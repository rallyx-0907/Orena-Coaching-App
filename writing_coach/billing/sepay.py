"""SePay + VietinBank: the domestic bank-transfer gateway (PR-MON-8, design revisions 5 + 6, D-MON-024).

SePay moves no money. It watches the owner's own VietinBank account and reports each booked transfer. The learner
pays by scanning a VietQR that Orena builds itself, with the order's payment code in the memo. This adapter only
verifies and normalizes; whether an order is paid is decided under the order's lock by
`BillingRepository.mark_paid_domestic`.

- Webhook: HMAC-SHA256 over `"{X-SePay-Timestamp}.{raw body}"`, header `X-SePay-Signature: sha256=<hex>`, a
  timestamp within 300 s, constant-time compare, all before any parsing.
- Identity (§3.1): the source id is `sepay:wh:<int>` (webhook) or `sepay:v2:<uuid>` (Transactions API v2). The
  payment event id is `sepay:ref:<account>:<reference>` when the bank reference exists, otherwise the source id.
  Two reference-less events are never equated.
- `transactionDate` is Vietnam time (UTC+7). It decides lateness under the lock.
- Acknowledgement: exactly `{"success": true}` (SePay counts nothing else as delivered).

Secrets (§3.2): the webhook secret and the API token never leave this object. No log, error, report or `repr` names
them, and the feed's errors carry the HTTP status only.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from writing_coach.billing.gateway import (
    CheckoutIntent,
    GatewayNotConfigured,
    PaymentFact,
    WebhookRejected,
    digest,
    hmac_sha256_hex,
    same,
)

TOLERANCE_SECONDS = 300
VIETNAM = timezone(timedelta(hours=7))
API_BASE = "https://userapi.sepay.vn/v2"
# The memo every payment carries: SePay needs `SEVQR` first for a VietinBank personal account (API banking).
MEMO_MARKER = "SEVQR"
# EMVCo purpose of transaction (tag 62, sub-tag 08) holds at most 25 characters.
PURPOSE_LIMIT = 25
ORDER_CODE_DIGITS = 12   # the order sequence starts at 100001; 12 digits is far beyond any real order count
_PREFIX = re.compile(r"^[A-Z]{2,8}$")
_ACCOUNT = re.compile(r"^[0-9]{6,19}$")
_BIN = re.compile(r"^[0-9]{6}$")
_NAPAS_GUID = "A000000727"
_TRANSFER_TO_ACCOUNT = "QRIBFTTA"


def _tlv(tag: str, value: str) -> str:
    if len(value) > 99:
        raise ValueError(f"EMVCo field {tag} is longer than 99 characters")
    return f"{tag}{len(value):02d}{value}"


def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no final xor): the EMVCo QR checksum."""

    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def vietqr_payload(*, bank_bin: str, account_number: str, amount_minor: int, purpose: str) -> str:
    """A dynamic VietQR (NAPAS 247, transfer to an account) for an exact VND amount and memo. Pure and deterministic."""

    if not _BIN.match(bank_bin) or not _ACCOUNT.match(account_number):
        raise ValueError("a VietQR needs a 6-digit bank BIN and a numeric account number")
    if type(amount_minor) is not int or amount_minor <= 0:
        raise ValueError("a VietQR amount is a positive whole number of dong")
    if not purpose or len(purpose) > PURPOSE_LIMIT or not purpose.isascii():
        raise ValueError(f"a VietQR memo is 1-{PURPOSE_LIMIT} ASCII characters")
    beneficiary = _tlv("00", bank_bin) + _tlv("01", account_number)
    merchant = _tlv("00", _NAPAS_GUID) + _tlv("01", beneficiary) + _tlv("02", _TRANSFER_TO_ACCOUNT)
    body = (_tlv("00", "01") + _tlv("01", "12") + _tlv("38", merchant) + _tlv("53", "704")
            + _tlv("54", str(amount_minor)) + _tlv("58", "VN") + _tlv("62", _tlv("08", purpose)) + "6304")
    return body + f"{crc16_ccitt_false(body.encode('ascii')):04X}"


@dataclass(frozen=True)
class Transfer:
    """One SePay transaction, from either source, normalized before it becomes a `PaymentFact`."""

    source_id: str
    transfer_type: str
    account_number: str
    code: str | None
    amount_minor: int | None
    reference: str
    transaction_at: datetime | None


def parse_transaction_date(value: object) -> datetime | None:
    """`YYYY-MM-DD HH:mm:ss` in Vietnam time, as UTC; None when it cannot be read (the decision then fails closed)."""

    if not isinstance(value, str):
        return None
    try:
        local = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return local.replace(tzinfo=VIETNAM).astimezone(UTC)


def _amount(value: object) -> int | None:
    return value if type(value) is int and value > 0 else None


class SePayGateway:
    name = "sepay"
    kind = "domestic"

    def __init__(self, *, webhook_secret: str, account_number: str, account_name: str, bank_bin: str,
                 payment_prefix: str, api_token: str = "", api_base: str = API_BASE, feed_enabled: bool = False) -> None:
        if not (webhook_secret and account_number and account_name and bank_bin and payment_prefix):
            raise GatewayNotConfigured("SePay needs SEPAY_WEBHOOK_SECRET, SEPAY_ACCOUNT_NUMBER, SEPAY_ACCOUNT_NAME, "
                                       "SEPAY_BANK_BIN and SEPAY_PAYMENT_PREFIX")
        if not _ACCOUNT.match(account_number) or not _BIN.match(bank_bin):
            raise GatewayNotConfigured("SEPAY_ACCOUNT_NUMBER is digits and SEPAY_BANK_BIN six digits")
        prefix = payment_prefix.strip().upper()
        if not _PREFIX.match(prefix):
            raise GatewayNotConfigured("SEPAY_PAYMENT_PREFIX is 2-8 letters")
        if len(f"{MEMO_MARKER} {prefix}") + ORDER_CODE_DIGITS > PURPOSE_LIMIT:
            raise GatewayNotConfigured("SEPAY_PAYMENT_PREFIX leaves no room for the order code in the VietQR memo")
        self._secret = webhook_secret
        self._token = api_token
        self.account_number = account_number
        self.account_name = account_name.strip()
        self.bank_bin = bank_bin
        self.prefix = prefix
        self.api_base = (api_base or API_BASE).rstrip("/")
        # PR-MON-8 §6.3: the recovery feed runs only with its token AND its switch; a token alone never starts it.
        self.feed_enabled = bool(feed_enabled and api_token)

    def __repr__(self) -> str:  # never the secret or the token
        return f"SePayGateway(account=***{self.account_number[-4:]}, prefix={self.prefix!r}, feed={self.feed_enabled})"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> SePayGateway:
        def get(name: str) -> str:
            return str(env.get(name, "")).strip()

        return cls(webhook_secret=get("SEPAY_WEBHOOK_SECRET"), account_number=get("SEPAY_ACCOUNT_NUMBER"),
                   account_name=get("SEPAY_ACCOUNT_NAME"), bank_bin=get("SEPAY_BANK_BIN"),
                   payment_prefix=get("SEPAY_PAYMENT_PREFIX"), api_token=get("SEPAY_API_TOKEN"),
                   api_base=get("SEPAY_API_BASE") or API_BASE,
                   feed_enabled=get("SEPAY_FEED_ENABLED").casefold() in {"1", "true", "yes", "on"})  # fmt: skip

    # ---- identity ---------------------------------------------------------------------------------------------

    def payment_event_id(self, transfer: Transfer) -> str:
        """§3.1: the bank reference when there is one (both sources agree on it), else the source's own id."""

        if transfer.reference:
            return f"sepay:ref:{transfer.account_number}:{transfer.reference}"
        return transfer.source_id

    def order_code(self, code: str | None) -> int | None:
        """The order the payment code names: the configured prefix followed by digits, matched exactly."""

        if code is None:
            return None
        value = code.strip().upper()
        if not value.startswith(self.prefix):
            return None
        digits = value[len(self.prefix):]
        if not digits.isdigit() or not 1 <= len(digits) <= ORDER_CODE_DIGITS or not digits.isascii():
            return None
        return int(digits)

    def to_fact(self, transfer: Transfer, *, payload_digest: str) -> PaymentFact:
        """One transfer as a `PaymentFact`. Outgoing money and other accounts are `ignored`; an incoming transfer to
        the configured account is a `payment`, with no order when its code is missing or foreign."""

        incoming = transfer.transfer_type == "in" and transfer.account_number == self.account_number
        order = self.order_code(transfer.code) if incoming else None
        return PaymentFact(
            gateway=self.name,
            event_id=self.payment_event_id(transfer),
            kind="payment" if incoming else "ignored",
            incarnation_hint=None,
            external_reference=str(order) if order is not None else None,
            amount_minor=transfer.amount_minor,
            currency="VND",
            provider_state="paid" if incoming else f"transfer_{transfer.transfer_type or 'unknown'}",
            payload_digest=payload_digest,
            extra={"source_id": transfer.source_id, "account_number": transfer.account_number,
                   "bank_reference": transfer.reference,
                   "transaction_at": transfer.transaction_at.isoformat() if transfer.transaction_at else ""},
        )

    # ---- webhook ----------------------------------------------------------------------------------------------

    def verify(self, headers: Mapping[str, str], body: bytes, *, now: datetime | None = None) -> PaymentFact:
        lowered = {str(key).casefold(): str(value) for key, value in headers.items()}
        signature = lowered.get("x-sepay-signature", "")
        stamp = lowered.get("x-sepay-timestamp", "").strip()
        if not signature or not stamp:
            raise WebhookRejected("missing_signature")
        if not stamp.isdigit():
            raise WebhookRejected("bad_timestamp")
        moment = now or datetime.now(UTC)
        if abs(moment.timestamp() - int(stamp)) > TOLERANCE_SECONDS:
            raise WebhookRejected("stale_timestamp")
        expected = "sha256=" + hmac_sha256_hex(self._secret, stamp.encode("ascii") + b"." + body)
        if not same(expected, signature):
            raise WebhookRejected("bad_signature")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WebhookRejected("unreadable_body") from error
        if not isinstance(payload, dict) or type(payload.get("id")) is not int:
            raise WebhookRejected("unreadable_body")
        code = payload.get("code")
        transfer = Transfer(
            source_id=f"sepay:wh:{payload['id']}",
            transfer_type=str(payload.get("transferType") or ""),
            account_number=str(payload.get("accountNumber") or ""),
            code=code if isinstance(code, str) else None,
            amount_minor=_amount(payload.get("transferAmount")),
            reference=str(payload.get("referenceCode") or "").strip()[:120],
            transaction_at=parse_transaction_date(payload.get("transactionDate")),
        )
        return self.to_fact(transfer, payload_digest=digest(body))

    @staticmethod
    def ack() -> dict[str, bool]:
        return {"success": True}

    # ---- checkout (G1): no provider call ----------------------------------------------------------------------

    def memo(self, order_code: int) -> str:
        return f"{MEMO_MARKER} {self.prefix}{int(order_code)}"

    def domestic_checkout(self, intent: CheckoutIntent, order: Mapping[str, Any]) -> dict[str, Any]:
        """The learner's transfer instructions for one committed order: the VietQR and the same facts in plain words."""

        if intent.price.currency != "VND":
            raise ValueError("SePay takes VND only")
        code = int(order["order_code"])
        memo = self.memo(code)
        return {
            "redirect_url": "",
            "qr": vietqr_payload(bank_bin=self.bank_bin, account_number=self.account_number,
                                 amount_minor=intent.price.amount_minor, purpose=memo),
            "transfer": {"bank_bin": self.bank_bin, "account_number": self.account_number,
                         "account_name": self.account_name, "amount_minor": intent.price.amount_minor,
                         "currency": "VND", "memo": memo},
        }

    # ---- recovery feed (G3, §6) ---------------------------------------------------------------------------------

    def feed_request(self, *, since_id: str | None, date_from: datetime | None, per_page: int = 100) -> dict[str, Any]:
        """Always page 1 (§6.2): the cursor moves, the page never does."""

        params: dict[str, str] = {"transfer_type": "in", "transaction_date_sort": "asc", "per_page": str(per_page),
                                  "page": "1"}  # fmt: skip
        if since_id:
            params["since_id"] = since_id
        elif date_from is not None:
            params["transaction_date_from"] = date_from.astimezone(VIETNAM).strftime("%Y-%m-%d %H:%M:%S")
        return {"method": "GET", "url": f"{self.api_base}/transactions", "params": params,
                "headers": {"Authorization": f"Bearer {self._token}"}}

    @staticmethod
    def feed_transfer(row: Mapping[str, Any]) -> Transfer:
        transfer_id = str(row.get("id") or "")
        code = row.get("code")
        return Transfer(
            source_id=f"sepay:v2:{transfer_id}",
            transfer_type=str(row.get("transfer_type") or ""),
            account_number=str(row.get("account_number") or ""),
            code=code if isinstance(code, str) else None,
            amount_minor=_amount(row.get("amount_in")),
            reference=str(row.get("reference_number") or "").strip()[:120],
            transaction_at=parse_transaction_date(row.get("transaction_date")),
        )

    @staticmethod
    def feed_row_digest(row: Mapping[str, Any]) -> str:
        return digest(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
