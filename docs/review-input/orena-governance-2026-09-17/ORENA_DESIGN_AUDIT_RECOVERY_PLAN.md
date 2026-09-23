# ORENA DESIGN AUDIT & RECOVERY PLAN
## Khôi phục ngôn ngữ thiết kế và North Star sau giai đoạn rebuild

**Mục đích tài liệu**  
Tài liệu này tổng hợp đánh giá hiện trạng Orena dựa trên các màn hình được review gần nhất, chỉ ra mức độ sai lệch so với phương châm rebuild ban đầu, và đưa ra nguyên tắc cùng kế hoạch cải thiện để AI/agent có thể audit và refactor lại sản phẩm một cách có hệ thống.

Tài liệu này **không phải yêu cầu "làm UI đẹp hơn"**. Mục tiêu chính là đưa Orena trở lại đúng bản chất sản phẩm đã đặt ra khi "đập đi xây lại".

---

# 1. NORTH STAR CỦA ORENA

Orena không phải là một bộ công cụ học ngôn ngữ.

Orena phải tạo cảm giác như một thế giới mà người học bước vào để khám phá, hiểu, giao tiếp và thể hiện bản thân bằng một ngôn ngữ khác.

> **Build a world worth entering, where language is something you live through—not a set of tools you operate.**

Một cách diễn đạt ngắn gọn hơn:

> **Library stores the world. Discover reveals the world. Learning tools help the learner interact with it.**

Và nguyên tắc cốt lõi:

> **Orena is content-first, curiosity-first, and human-intention-first. Skills are capabilities beneath the experience, not the primary way the world is organized.**

---

# 2. PHƯƠNG CHÂM THIẾT KẾ BAN ĐẦU CẦN GIỮ

## 2.1. World before tools

Người dùng không nên cảm thấy mình đang mở một dashboard gồm:

- Reading
- Listening
- Speaking
- Writing
- Vocabulary
- Grammar
- Practice

Những thứ trên là **năng lực hoặc cơ chế học**, không nên định nghĩa toàn bộ thế giới Orena.

Orena trước hết phải tạo được cảm giác:

- có thứ gì đó đáng xem;
- có một câu chuyện đáng bước vào;
- có một giọng nói đáng nghe;
- có một ý tưởng đáng khám phá;
- có một nội dung đủ hấp dẫn để người học muốn tiếp tục.

---

## 2.2. Curiosity before curriculum

Trước khi người dùng nghĩ:

> "Hôm nay mình phải học Listening."

Orena nên khiến họ nghĩ:

> "Cái này trông thú vị, mình muốn xem thử."

"Follow your curiosity" phải là một nguyên tắc UX thật sự, không chỉ là slogan cạnh logo.

---

## 2.3. Content first

Sách, video, audio, story, article, passage, conversation và các nội dung khác phải là **portal** để bước vào trải nghiệm.

Ví dụ:

> "The last train home"

không nên chỉ là:

> Reading · B1–B2 · 3 min

Nó trước hết phải là **một câu chuyện / một thế giới nhỏ / một nội dung có sức hút**.

Sau khi người dùng bước vào đó, các năng lực học mới xuất hiện:

- đọc;
- nghe;
- xem transcript;
- tra nghĩa;
- pronunciation;
- pinyin;
- grammar;
- save vocabulary;
- shadowing;
- speaking;
- writing;
- review.

---

## 2.4. Human intention before learning mechanic

Thay vì chỉ trình bày:

- Dictation
- Shadowing
- Speaking
- Writing
- Grammar

nên ưu tiên cách diễn đạt dựa trên ý định của người học.

Ví dụ:

- Catch every word → Dictation
- Sound more like them → Shadowing
- Say what you think → Speaking
- Put it into words → Writing
- See how this works → Grammar / pattern

Cơ chế học vẫn tồn tại, nhưng **không nên là thứ đầu tiên người dùng phải nghĩ đến**.

---

## 2.5. AI stays backstage

Orena không nên trông như "một AI language learning app".

AI nên đứng phía sau để:

- giải thích;
- gợi ý;
- thích nghi;
- sinh nội dung khi cần;
- đồng bộ transcript;
- tạo quiz;
- phân tích writing;
- hỗ trợ speaking;
- kết nối các nội dung học.

Người dùng nên tương tác với **language và content**, không phải với "AI feature".

---

## 2.6. Warm, tactile, alive

Ngôn ngữ thị giác phải:

- ấm;
- có chiều sâu;
- có personality;
- có motion vừa đủ;
- có texture;
- có tính editorial;
- trưởng thành nhưng vẫn playful;
- tránh generic SaaS;
- tránh generic AI UI;
- tránh phẳng và vô cảm.

Warmth không đến từ việc thêm nhiều màu.  
Nó đến từ:

- content imagery;
- typography;
- materiality;
- hierarchy;
- motion;
- irregularity có kiểm soát;
- cách các phần liên kết với nhau.

---

## 2.7. Focus when inside a learning experience

Khi người dùng đã bước vào:

- một chapter;
- một video;
- một writing session;
- một speaking session;

thì thế giới bên ngoài nên lùi lại.

Không nên cố "worldify" mọi màn hình.

Khi học:

> **world recedes, content comes forward.**

---


# 2A. CLARITY FIRST — BEGINNER-SAFE PRODUCT PRINCIPLE

Khái niệm "world" là **ngôn ngữ nội bộ để định hướng thiết kế**, không phải một metaphor mà learner phải học để dùng Orena.

North Star phải được cân bằng bằng ba nguyên tắc:

> **Clarity first. Curiosity next. Depth over time.**

và:

> **Simple front door. Deep world behind it.**

Một người:

- chưa từng học ngoại ngữ;
- chưa từng dùng app học ngôn ngữ;
- chỉ đơn giản nghĩ "tôi muốn bắt đầu học tiếng Anh / tiếng Trung";

phải biết phải làm gì trong vài giây đầu tiên.

Orena **không được yêu cầu người dùng học cách sử dụng Orena trước khi họ có thể bắt đầu học ngôn ngữ**.

## "World" nghĩa là gì

"World" KHÔNG có nghĩa:

- fantasy;
- lore;
- gọi learner là traveler;
- đặt tên navigation khó hiểu;
- dùng metaphor thay cho chức năng;
- viết nhiều slogan về hành trình;
- biến app thành game world nếu điều đó làm giảm clarity.

"World" chỉ có nghĩa:

- có nhiều nội dung thật để xem, đọc, nghe và khám phá;
- content có hình ảnh, âm thanh và personality;
- các nội dung có thể liên hệ với nhau;
- learner cảm thấy app có chiều sâu hơn một bộ menu chức năng.

> **Never explain the Orena philosophy to the learner. Let them experience it.**

## Guided path và Explore phải cùng tồn tại

Orena phải phục vụ ít nhất hai nhu cầu:

### Guided path
Dành cho người nghĩ:

> "Tôi chưa biết học gì. Hãy dẫn tôi."

Entry point phải rất rõ, ví dụ:

- Start here
- Start learning
- Continue
- Your first 5 minutes

Không cần learner hiểu curriculum architecture.

### Explore
Dành cho người muốn:

> "Tôi muốn tự xem có gì thú vị."

Explore/Discover có thể dùng:

- books;
- stories;
- short videos;
- audio;
- people;
- everyday situations;
- themes;
- topics.

Hai con đường phải dùng chung content/learning system, không tạo hai sản phẩm riêng.

## Navigation được phép đơn giản và trực tiếp

Không được biến các label rõ ràng thành những câu poetic khó hiểu chỉ để "có chất".

Các label sau hoàn toàn được phép khi chúng giúp clarity:

- Reading
- Listening
- Speaking
- Writing
- Vocabulary
- Library
- Practice

Personality nên đến từ:

- artwork;
- content;
- composition;
- icon;
- color;
- motion;
- interaction;

không phải bằng cách làm tên chức năng khó hiểu.

## Beginner experience

Với learner mới hoàn toàn, màn hình đầu nên ưu tiên:

1. ngôn ngữ muốn học;
2. mức hiện tại;
3. một CTA bắt đầu rõ;
4. nội dung đầu tiên ngắn và dễ;
5. vài lựa chọn khám phá phụ nếu muốn.

Không đưa một novice vào một catalogue quá lớn mà không có đường dẫn.

## Adaptive prominence

Home/Discover có thể thay đổi emphasis theo trạng thái learner:

### New learner
- Start learning là primary.
- Explore là secondary.
- Ít choice.
- Nội dung ngắn, dễ hiểu.

### Returning learner
- Continue là primary.
- Discovery mở rộng dần.
- Recall xuất hiện khi có dữ liệu thật.

### Experienced learner
- Continue / new content / recommendations / library có thể có prominence lớn hơn.
- Guided path vẫn tồn tại nhưng không cần chiếm hết màn hình.


# 3. KẾT LUẬN HIỆN TRẠNG

Orena hiện tại **không xấu**, và nhiều thành phần riêng lẻ đã khá tốt.

Nhưng tổng thể đã bị trượt khỏi North Star.

Mô tả chính xác nhất cho trạng thái hiện tại là:

> **Poetic copy over SaaS architecture.**

Các câu chữ có hồn:

- Follow your curiosity
- The world has something to say.
- Something worth reading
- A small moment. A little more yours.
- Find the words you mean.

Nhưng architecture bên dưới vẫn chủ yếu là:

> sidebar → module → filter → search → card → list → metric → panel

Đây vẫn là ngôn ngữ của một learning platform / SaaS dashboard.

---

# 4. SAI LỆCH LỚN NHẤT: ORENA ĐANG QUAY LẠI FEATURE DASHBOARD

Sidebar hiện tại có các nhóm:

### A bigger world
- Discover
- Continue
- Reading
- Listening

### Make it yours
- Practice
- Writing
- Speaking
- Patterns & meaning

### Your growing world
- My content
- My language
- Recall

Tên nhóm rất đúng tinh thần Orena.

Nhưng nội dung bên trong lại quay lại taxonomy truyền thống:

- Reading
- Listening
- Writing
- Speaking
- Practice
- Vocabulary

Kết quả là:

> **poetic framing + conventional product architecture**

Nó tạo cảm giác Orena chỉ đang "đổi tên cho đẹp" nhưng mô hình sản phẩm bên dưới chưa thay đổi đủ sâu.

---

# 5. REVIEW THEO TỪNG MÀN HÌNH

---

# 5.1. DISCOVER

## Hiện trạng

Discover đang tổ chức nội dung theo rail:

- Continue learning
- Reading
- Listening
- ...

Về UX thuần túy, rail ngang là hợp lý.

Nhưng cách phân chia theo skill đang tạo vấn đề lớn.

## Vấn đề

Người dùng vào Discover và bị hỏi ngầm:

> "Bạn muốn Reading hay Listening?"

Trong khi đúng tinh thần Orena phải là:

> "Hôm nay điều gì khiến bạn tò mò?"

Discover đang là **content catalogue theo modality**.

Nó chưa phải **discovery surface**.

## Ví dụ sai lệch

"The last train home" là một content title rất có tiềm năng.

Nhưng UI biến nó thành:

> Reading · B1–B2 · 3 min

và đặt cạnh nhiều asset khác trong cùng một row.

Một câu chuyện có atmosphere bị biến thành "learning asset".

## Cần sửa

Discover phải ưu tiên:

- story;
- topic;
- mood;
- idea;
- person;
- moment;
- theme;
- curiosity;
- real-world context.

Ví dụ các rail tốt hơn:

- Stories for a rainy evening
- Worth disappearing into
- Voices from somewhere else
- Tiny things you can finish tonight
- Things you never thought about
- A little strange, a little familiar
- From the world outside
- Continue where you left off
- Because you liked...
- Something new in Chinese
- Listen to someone else's world

Các rail có thể chứa mixed content:

- book;
- article;
- audio;
- video;
- story;
- conversation.

Không cần ép mỗi rail phải là một skill.

---

# 5.2. CONTINUE

## Hiện trạng

Continue hiện có vài card rồi rất nhiều khoảng trống.

Ví dụ:

- The cosmic calendar
- Alice's Adventures in Wonderland
- Contents

## Vấn đề

Continue đang được hiểu như:

> danh sách item chưa hoàn tất.

Đây là logic database, không phải continuity.

## Cần sửa

Continue nên mang nghĩa:

> **nơi thế giới của tôi tiếp tục.**

Ví dụ:

- "You left Alice beside the pool of tears."
- "Yesterday you heard the first 46 seconds of The Cosmic Calendar."
- "You saved 3 expressions from The last train home."
- "You were halfway through a conversation about..."

Card nên thể hiện:

- context;
- progress;
- nơi đang dở;
- lý do để quay lại.

Không chỉ hiện title + type.

---

# 5.3. READING LANDING PAGE

## Điểm tốt

Copy:

> Read something through

và:

> Highlight anything to ask about it...

đúng hướng.

Nó nói về trải nghiệm, không nói "Improve Reading Skill".

## Vấn đề

Phần dưới lại trở thành:

- Library
- Search
- Filter
- Result count
- Content list

Tức là một content manager / catalogue.

"Something worth reading" là một heading rất tốt, nhưng ngay dưới lại là search/filter, làm mất cảm giác khám phá.

## Cần sửa

Search/filter vẫn cần, nhưng nên là secondary control.

Primary surface nên là:

- editorial shelves;
- cover-first browsing;
- curated themes;
- recommended stories;
- short reads;
- long reads;
- continue reading;
- recently added;
- topic clusters.

---

# 5.4. BOOK LIBRARY

## Hiện trạng

Các cover dạng placeholder:

- chữ A;
- chữ S;
- khối màu.

## Vấn đề

Đây chưa tạo cảm giác là một thư viện sách.

Nếu gọi là Library, bìa sách phải là yếu tố chính.

## Cần sửa

Card sách:

- cover lớn;
- title vừa đủ;
- metadata tối thiểu;
- không nhồi text.

Detail mới hiển thị:

- author;
- level;
- language;
- description;
- chapter count;
- progress;
- source / rights;
- audio availability;
- related content.

---

# 5.5. BOOK DETAIL

## Hiện trạng

Alice's Adventures in Wonderland có:

- cover placeholder;
- title;
- author;
- danh sách chapter.

## Vấn đề

Nó giống file browser / table of contents.

Chưa có cảm giác đang bước vào một cuốn sách.

## Cần sửa

Có thể thêm:

- cover thật;
- progress;
- current chapter;
- short intro;
- reading time;
- continue CTA;
- chapter list;
- optional audiobook;
- related vocabulary;
- related story/audio nếu có.

Không cần trang trí quá mức.

---

# 5.6. READER

## Điểm đúng

Reader nên sạch và tập trung.

Không cần biến thành một scene hay fantasy.

## Vấn đề

- sidebar đầy đủ vẫn hiện;
- line length quá dài;
- heading quá lớn;
- hierarchy đầu trang bị lỗi;
- progress và book title dính nhau;
- learning layer chưa thấy đủ;
- cảm giác vẫn là app shell.

## Cần sửa

Reader nên có:

- tối ưu line length;
- typography reading-friendly;
- collapse/hide sidebar;
- sticky minimal reading controls;
- progress rõ;
- chapter navigation rõ;
- bookmark;
- font control;
- highlight;
- sentence/paragraph interaction;
- explain;
- meaning;
- pronunciation;
- pinyin nếu cần;
- save vocabulary;
- grammar pattern;
- optional quiz;
- recall linkage.

Đây là một yêu cầu cốt lõi của Orena.

---

# 5.7. LISTENING LANDING PAGE

## Điểm tốt

Headline:

> The world has something to say.

là một trong những câu tốt nhất hiện tại.

Nó nói về thế giới trước, kỹ năng sau.

## Vấn đề

Phần dưới trở thành:

- Listening library
- Search
- Level filter
- grid
- Continue listening
- My media

Nó giống media manager / Plex / podcast library.

## Cần sửa

Listening discovery nên có:

- people;
- voices;
- places;
- moments;
- topics;
- stories;
- short clips;
- long-form;
- real-world source.

Library/search vẫn có nhưng không nên chiếm toàn bộ experience.

---

# 5.8. LISTENING EXPERIENCE

Ảnh hiện tại chủ yếu thể hiện selection layer.

Core learning layer phải đảm bảo:

- synchronized transcript;
- current word highlight;
- current sentence highlight;
- tap word;
- meaning;
- pronunciation;
- pinyin;
- sentence explanation;
- save vocabulary;
- replay line;
- slow down;
- shadowing;
- speaking;
- optional quiz;
- progress.

Nếu video/audio chỉ tồn tại như media card, Orena chưa tận dụng đúng tiềm năng.

---

# 5.9. PRACTICE

## Điểm tốt

Đây là màn gần North Star nhất.

Copy:

> A small moment. A little more yours.

và:

> Choose an intention.

rất đúng.

Card:

> The intention is yours. The language comes from somewhere real.

cũng đúng hướng.

## Vấn đề

Danh sách bên phải lại là:

- Dictation
- Shadowing
- Speaking
- Writing
- Grammar

Tức là cuối cùng vẫn quay lại exercise taxonomy.

## Cần sửa

Giữ mechanic bên dưới, nhưng humanize entry point.

Ví dụ:

- Catch every word
- Sound more like them
- Say what you think
- Put it into words
- See how this works

Learning mechanic có thể hiện như subtitle hoặc detail.

---

# 5.10. WRITING

## Điểm tốt

Focus mode khá hợp lý.

Split pane editor / review là đúng chức năng.

## Vấn đề

Hiện tại nó giống:

- Grammarly;
- AI writing assistant;
- enterprise editor.

Prompt:

> What are you writing?

nằm dưới editor, trong khi đây là intention/context.

## Cần sửa

Context phải xuất hiện trước hoặc cạnh editor.

Flow đúng:

1. what do you want to say?
2. who is it for?
3. optional tone/context
4. write
5. review
6. explain why
7. revise
8. save useful expression

Review không chỉ sửa lỗi mà nên giúp learner hiểu:

- what changed;
- why;
- naturalness;
- alternative expression;
- pattern worth keeping.

---

# 5.11. VOCABULARY / MY LANGUAGE

## Hiện trạng

Dashboard có:

- Saved
- Learning
- Due today
- Mastered

và Daily Vocabulary Feed.

## Vấn đề

Metrics đang có quá nhiều visual authority.

"My language" bị thu hẹp thành vocabulary database.

## Cần sửa

"My Language" phải rộng hơn:

- saved words;
- expressions;
- phrases;
- sentence patterns;
- pronunciation;
- personal examples;
- mistakes;
- grammar notes;
- language collected from content.

Daily Feed là concept đúng.

Nó nên là một góc nhỏ, tactile, serendipitous.

Không nên trở thành một dashboard KPI.

---

# 5.12. SIDEBAR

## Vấn đề

Sidebar luôn luôn xuất hiện, kể cả:

- reader;
- writing;
- listening;
- focused session.

Điều này làm giảm immersion trong các trải nghiệm cần tập trung.

> **Lưu ý:** `Platform Admin` chỉ xuất hiện trên tài khoản quản trị của chủ app, không thuộc learner experience chung và **không được xem là vấn đề cần refactor trong audit này**.

## Cần sửa

- Khi vào focused experience, sidebar nên collapse/minimize.
- Primary navigation nên nhẹ hơn trong reader/listening/writing session.
- "Bring something in" có thể giữ như utility nhưng không nên chiếm semantic prominence quá lớn.

---

# 6. VẤN ĐỀ HÌNH ẢNH VÀ ASSET

## 6.1. Mascot đang bị dùng như sticker

Mascot xuất hiện đẹp nhưng thường chỉ làm nhiệm vụ "lấp chỗ trống".

Ví dụ:

- Reading → mascot đọc sách;
- Listening → mascot đeo headphone;
- Practice → mascot đeo balo.

## Cần sửa

Mascot chỉ nên xuất hiện khi có vai trò:

- guide;
- reaction;
- progress;
- onboarding;
- empty state;
- moment of encouragement;
- contextual companion.

Không nên đặt mascot chỉ vì một hero trống.

---

## 6.2. Chưa có visual grammar thống nhất

Hiện tại có:

- scenic illustration;
- mascot sticker;
- abstract placeholder;
- text cover;
- real thumbnail.

Cần xác định luật.

Ví dụ:

### Real-world video/audio
→ documentary/real thumbnail

### Orena-created story
→ illustrated scene

### Book
→ actual cover / designed cover

### Exercise
→ symbolic/graphic visual

### Mascot
→ contextual companion

---


# 6A. ART DIRECTION PHẢI LÀ ƯU TIÊN CẤP 1

Phần artwork đã được đề cập trong audit trước, nhưng **chưa đủ mạnh** so với mức độ quan trọng thực tế. Từ thời điểm này, artwork phải được xem là một phần của **core design language**, không phải lớp trang trí bổ sung.

## Mục tiêu

Orena phải có cảm giác:

- ít lời;
- nhiều hình ảnh;
- giàu màu sắc;
- sinh động;
- có personality;
- nhận ra ngay là cùng một thế giới;
- không giống một dashboard beige với vài sticker mascot.

## Luật quan trọng

### 1. Một visual universe thống nhất

Mọi artwork phải nhìn như thuộc cùng một hệ.

Không được để:

- mascot 3D/cartoon một kiểu;
- landscape painterly một kiểu khác;
- thumbnail geometric placeholder một kiểu khác;
- book cover chỉ có chữ cái;
- icon line-art xám;
- card illustration từ nhiều nguồn không liên quan;

cùng tồn tại mà không có art direction rõ ràng.

Agent phải xác định và tuân thủ một **Art Bible** chung cho:

- mascot;
- scene illustration;
- content thumbnail;
- book cover;
- icon;
- badge;
- empty state;
- decorative element;
- pattern/background;
- social/brand asset.

### 2. Artwork không chỉ để lấp chỗ trống

Artwork phải làm ít nhất một trong các việc sau:

- kể chuyện;
- tạo mood;
- tạo curiosity;
- định danh content;
- giúp phân biệt category;
- tạo continuity;
- hướng sự chú ý;
- tăng cảm giác "world".

Nếu artwork chỉ tồn tại vì một hero đang trống thì không đạt.

### 3. Content image phải là nhân vật chính

Đặc biệt ở Discover / Library / Reading / Listening:

- cover;
- thumbnail;
- scene;
- visual cue;

phải có visual authority cao hơn metadata và text mô tả.

Người dùng nên nhìn thấy thứ đáng khám phá trước, rồi mới đọc thông tin.

### 4. Màu sắc được phép sống động

Không ép toàn bộ Orena vào beige + navy + sage ở mức độ quá an toàn.

Brand palette vẫn là nền chung, nhưng content artwork có thể dùng:

- cam;
- đỏ;
- vàng;
- xanh lam;
- xanh lục;
- tím;
- cyan;
- màu tương phản mạnh;

miễn có kiểm soát và thuộc cùng art direction.

Mục tiêu không phải "pastel SaaS".  
Mục tiêu là **warm, vivid, playful, editorial, memorable**.

### 5. Icon không nên chỉ là line icon xám

Những icon có vai trò trực tiếp trong trải nghiệm có thể:

- có màu;
- có shape;
- có filled state;
- có small illustration;
- có tactile feedback;
- có motion nhẹ.

Không biến mọi thứ thành monochrome utility icon nếu điều đó làm mất personality.

### 6. Placeholder phải biến mất khỏi production experience

Các thumbnail kiểu:

- Aa 字;
- chữ A / S / T / M;
- abstract block lặp lại;
- khung trống;
- generic geometric placeholder;

chỉ được dùng trong development.

Không được coi là visual language cuối cùng của sản phẩm.

---

# 6B. LESS WORDS, MORE LIFE

Một vấn đề lớn khác là Orena đang có nguy cơ dùng quá nhiều:

- giant header;
- eyebrow;
- slogan;
- descriptive paragraph;
- poetic sentence;
- helper copy.

Điều này trái với hướng mong muốn.

## Nguyên tắc mới

> **Show first. Say only what is needed.**

Orena không nên giải thích cảm xúc bằng nhiều câu chữ nếu artwork, content và interaction có thể tự truyền tải.

## Không được lạm dụng hero

Pattern sau không được dùng mặc định cho mọi page:

- eyebrow
- giant headline
- poetic slogan
- paragraph
- mascot bên phải

Chỉ dùng hero lớn khi nó thực sự cần thiết.

## Hạn chế slogan

Không mỗi màn hình đều cần một câu kiểu:

- "The world has something to say."
- "A small moment. A little more yours."
- "Read something through."
- "Something worth reading."

Một số câu có thể giữ vì chúng có personality, nhưng phải dùng **rất tiết kiệm**.

Nếu một màn hình cần 2–3 câu để nói người dùng đang ở đâu, hierarchy hoặc artwork đang chưa làm đủ việc.

## Hướng ưu tiên

Thay vì:

> LISTENING  
> The world has something to say.  
> Follow a voice at your pace. Stay with the meaning, or step inside a single line.

Có thể ưu tiên:

- một visual mạnh;
- title ngắn;
- content rails;
- icon/thumbnail;
- interaction cue.

Ví dụ:

> **Listen**

sau đó để nội dung và hình ảnh làm phần còn lại.

## Copy budget

Mỗi screen nên có một "copy budget".

Ưu tiên:

1. content title;
2. action;
3. essential context;
4. metadata;
5. optional explanation.

Slogan và prose marketing là ưu tiên thấp.

---

# 6C. ART BIBLE TỐI THIỂU CẦN ĐƯỢC TẠO

Trước khi refactor UI hàng loạt, agent phải tạo một Art Bible ngắn nhưng rõ.

Art Bible phải xác định:

## Character / Mascot
- shape language;
- proportion;
- face/expression;
- outline/no outline;
- lighting;
- texture;
- perspective;
- allowed poses;
- allowed use cases;
- forbidden use cases.

## Scene Illustration
- rendering style;
- color saturation;
- lighting;
- environmental depth;
- composition;
- level of detail;
- relation to mascot;
- relation to brand palette.

## Content Thumbnail
- when to use real image;
- when to use illustration;
- crop rules;
- title overlay rules;
- category markers;
- duration/level placement.

## Book Cover
- cover-first;
- no single-letter placeholder;
- coherent layout system;
- genre variation allowed;
- title legibility;
- avoid fake book cover look.

## Icons
- icon family;
- stroke/fill rules;
- color rules;
- active/inactive state;
- small decorative icons;
- learning-action icons.

## Background / Pattern
- use sparingly;
- avoid generic gradients/blobs;
- support atmosphere, never compete with content.

## Motion
- subtle;
- tactile;
- purposeful;
- card swipe / flip / snap;
- icon feedback;
- mascot reaction only when meaningful.

---

# 6D. DESIGN CONSTITUTION BỔ SUNG

Thêm các luật sau:

### Rule A
Orena should be **visually expressive before verbally explanatory**.

### Rule B
Use fewer headings and fewer slogans. Do not turn poetic copy into a template.

### Rule C
Artwork across the product must follow one shared Art Bible.

### Rule D
Real content imagery and designed covers are preferred over generic placeholders.

### Rule E
Colorful does not mean random. Vivid color is encouraged inside a controlled visual system.

### Rule F
Icons may carry personality and color; do not default everything to gray line icons.

### Rule G
If a screen feels empty, do not automatically add a slogan or mascot. Fix composition, content density, imagery, or hierarchy first.

### Rule H
If an artwork has no narrative, navigational, emotional, or semantic role, remove it.

# 7. TYPOGRAPHY

Một hướng tốt đang tồn tại:

- sans-serif cho interface;
- serif cho story/editorial content.

Nên biến thành luật:

> **UI speaks sans. Stories speak serif.**

Không dùng serif/sans tùy component ngẫu nhiên.

---

# 8. PALETTE

Palette hiện tại:

- warm beige;
- navy;
- orange;
- sage;

đúng hướng.

Không nên chữa bằng cách thêm nhiều màu.

Vấn đề hiện tại là:

- surface quá phẳng;
- card treatment lặp lại;
- thiếu depth;
- thiếu material hierarchy.

---

# 9. QUÁ NHIỀU "SAFE RECTANGLES"

Hiện tại gần như mọi thứ đều là:

- white rounded card;
- white panel;
- white input;
- white thumbnail frame;
- horizontal divider.

Đây là visual grammar của SaaS.

Không cần loại bỏ card.

Nhưng card không nên là **đơn vị cơ bản của toàn bộ thế giới Orena**.

---

# 10. HERO PATTERN ĐANG BỊ LẶP

Nhiều trang đang dùng:

- eyebrow
- giant headline
- paragraph
- mascot bên phải

Nếu mọi trang đều dùng cùng một công thức, cảm xúc sẽ bị "component hóa".

Sau vài trang người dùng sẽ nhận ra:

> đây là HeroHeader component.

Không phải mọi section đều cần hero lớn.

---

# 11. LIBRARY KHÔNG MÂU THUẪN VỚI NORTH STAR

Việc đưa:

- hàng trăm sách;
- hàng nghìn video;
- audio;
- story;
- article;

vào Orena là **đúng hướng**.

Thậm chí đây là yếu tố quan trọng để "Follow your curiosity" có nội dung thật để vận hành.

Vấn đề không phải có Library hay không.

Vấn đề là:

> Library phải là hạ tầng chứa thế giới, không được trở thành toàn bộ khuôn mặt của Orena.

---

# 12. PHÂN TÁCH LIBRARY VÀ DISCOVER

## Library

Library là nơi người dùng biết mình muốn tìm gì.

Nó có thể có:

- Books
- Stories
- Articles
- Video
- Audio
- Search
- Filter
- Language
- Level
- Source
- Topic
- Duration
- Saved
- Started

Đây là nơi UI có thể thực dụng.

## Discover

Discover là nơi Orena lựa chọn cách làm lộ ra những phần thú vị của Library.

Discover không nên chỉ là:

- Reading
- Listening
- Speaking
- Writing

Nó nên là:

- story;
- theme;
- mood;
- idea;
- people;
- places;
- short-form;
- long-form;
- real-world discovery;
- personal recommendation.

---

# 13. KHÔNG NHÂN BẢN CONTENT THEO SKILL

Ví dụ có một video:

> Why do cats purr?

Không nên tạo các bản riêng:

- Listening resource
- Vocabulary resource
- Speaking resource
- Practice resource

Nó phải là **một content object**.

Từ một content object, learner có thể:

- watch/listen;
- view transcript;
- tap word;
- save word;
- explain sentence;
- see grammar;
- shadow;
- speak;
- write;
- review.

---

# 14. ARCHITECTURE NÊN HƯỚNG TỚI

```text
CONTENT LIBRARY
│
├── Book
├── Story
├── Article
├── Video
├── Audio
└── Conversation
        │
        ▼
DISCOVERY / EXPERIENCE LAYER
│
├── Discover
├── Continue
├── Reading
├── Listening
├── Library
└── Recommendations
        │
        ▼
LEARNING ACTIONS
│
├── Explain
├── Vocabulary
├── Pronunciation
├── Grammar / Pattern
├── Shadowing
├── Speaking
├── Writing
└── Recall
```

Điểm quan trọng:

> Reading và Listening là **views / modalities của cùng một content world**, không nên là các silo dữ liệu hoàn toàn riêng biệt.

---

# 15. CÁC THỨ NÊN GIỮ

Không nên "đập đi lần nữa" theo kiểu xóa sạch mọi thứ.

Những thứ nên giữ:

- logo Orena;
- orange/navy;
- warm neutral background;
- sage secondary;
- mascot;
- Follow your curiosity;
- serif editorial typography;
- "The world has something to say";
- "Something worth reading";
- "A small moment. A little more yours";
- horizontal rails;
- intent-centric Practice;
- Daily Vocabulary Feed;
- clean Reading/Writing surfaces;
- concise navigation;
- AI backstage approach.

---

# 16. CÁC THỨ KHÔNG NÊN LÀM

## Không chữa "worldness" bằng decoration

Không được chỉ thêm:

- background landscape;
- gradient;
- blob;
- star;
- floating shapes;
- random animation;
- mascot ở mọi nơi.

Worldness phải đến từ **content architecture trước**.

---

## Không xóa Reading / Listening

Reading và Listening vẫn là useful shortcuts.

Người dùng đôi khi biết rất rõ:

> hôm nay tôi muốn nghe.

Vấn đề là đừng để chúng định nghĩa toàn bộ Orena.

Chúng nên là **doors**, không phải toàn bộ thế giới.

---

## Không làm Library fantasy

Library có thể rất sạch và thực dụng.

Ví dụ:

### Continue reading
[cover] [cover] [cover]

### Stories & fiction
[cover] [cover] [cover]

### Science & ideas
[cover] [cover] [cover]

### Short reads
[cover] [cover] [cover]

### Explore all books →

Không cần decoration dư thừa.

Nội dung thật chính là visual richness.

---

# 17. DESIGN CONSTITUTION ĐỀ XUẤT

Mọi agent phải tuân thủ các luật sau:

### Rule 1
Orena is **content-first**, not feature-first.

### Rule 2
Curiosity comes before curriculum.

### Rule 3
Human intention comes before learning mechanic.

### Rule 4
Skills are capabilities beneath the experience.

### Rule 5
AI stays backstage.

### Rule 6
Content should feel like something worth entering, not a database record.

### Rule 7
Discover must not organize the whole world only by Reading / Listening / Speaking / Writing.

### Rule 8
Library may be practical and searchable.

### Rule 9
Focused learning screens should reduce navigation noise.

### Rule 10
Learning assistance must remain within reach during content consumption.

### Rule 11
Real content should provide visual richness before decorative artwork is added.

### Rule 12
Do not add decoration to fake immersion.

### Rule 13
UI speaks sans. Stories speak serif.

### Rule 14
Do not expose internal taxonomy/provenance unless useful to the learner.

---


### Rule 16
**Clarity first. Curiosity next. Depth over time.**

### Rule 17
The front door must be simple enough for a learner who has never used a language-learning app.

### Rule 18
"World" is an internal design principle, not learner-facing lore or mandatory metaphor.

### Rule 19
Never replace a clear navigation label with poetic wording if comprehension becomes worse.

### Rule 20
Guided learning and open exploration must coexist.

### Rule 21
A new learner must always have one obvious next action.

### Rule 22
Never explain Orena's philosophy to the learner when the interface can demonstrate it through content, artwork and interaction.

# 18. KIỂM TRA "ORENA TEST"

Trước khi chấp nhận bất kỳ màn hình mới nào, đặt câu hỏi:

> **Nếu xóa tất cả các nhãn Reading, Listening, Speaking, Writing khỏi màn hình này, người học vẫn có lý do để muốn bước vào không?**

Nếu câu trả lời là **không**, màn hình đó chưa đạt North Star.

Ví dụ:

- "The last train home" → PASS
- "The world has something to say." → PASS
- "A small moment. A little more yours." → PASS
- một rail chỉ có nhãn "Reading" → FAIL
- một grid "Listening Library" không có contextual discovery → FAIL

---

# 19. ƯU TIÊN REFACTOR

Không nên refactor toàn bộ app cùng lúc.

## Phase 1 — Freeze North Star

Viết/đóng băng:

- Design Constitution;
- IA principles;
- visual grammar;
- content-first rule;
- acceptance criteria.

Không cho agent tự suy diễn lại.

## Phase 2 — Refactor Discover

Đây là nơi quyết định Orena là sản phẩm gì.

Mục tiêu:

- giảm taxonomy skill;
- tăng thematic discovery;
- mixed content;
- stronger imagery;
- more editorial curation;
- retain horizontal rail behavior;
- do not overdecorate.

## Phase 3 — Continue

Biến Continue từ item list thành continuity.

## Phase 4 — Library / Reading / Listening

Tách:

- discovery;
- library;
- modality view;
- search/filter.

Không lẫn tất cả vào một trang.

## Phase 5 — Focus experiences

Refine:

- reader;
- listening player;
- writing;
- speaking;
- practice.

## Phase 6 — My Language / Recall

Mở rộng từ vocabulary database thành personal language system.

---

# 20. ACCEPTANCE CRITERIA CHO DISCOVER

Một Discover mới chỉ được chấp nhận nếu:

- Không bị chia chủ yếu theo 4 kỹ năng truyền thống.
- Có ít nhất một số rail mixed content.
- Content title và imagery là thứ thu hút trước.
- Level/type là secondary metadata.
- Có continuity.
- Có personal relevance nhưng không biến thành KPI dashboard.
- Không thêm visual noise để giả immersive.
- Không dùng mascot chỉ để lấp khoảng trống.
- Mobile vẫn nhìn thấy nhiều world-entry points trong viewport đầu.
- Horizontal rail hoạt động đúng, không phá vertical scroll.
- UI không giống Netflix clone một cách máy móc.
- Discover tạo được ít nhất một cảm giác: "Tôi muốn bấm vào cái này."

---

# 21. ACCEPTANCE CRITERIA CHO LIBRARY

Library được phép practical hơn Discover.

Yêu cầu:

- search rõ;
- filter rõ;
- cover/thumbnail là chính;
- metadata tối giản trên card;
- detail mở rộng khi vào sâu;
- hỗ trợ hàng trăm / hàng nghìn content;
- không tạo silo duplicate giữa Reading/Listening;
- content object có thể phục vụ nhiều learning actions;
- responsive tốt trên mobile;
- không biến thành admin content manager.

---

# 22. ACCEPTANCE CRITERIA CHO READER

- content-first;
- minimal shell;
- readable line length;
- progress rõ;
- chapter nav;
- highlight;
- word tap;
- meaning;
- pronunciation/pinyin;
- sentence explanation;
- grammar note;
- save vocabulary;
- optional quiz;
- recall linkage;
- support English + Chinese;
- không bắt learner rời reader để dùng core learning tools.

---

# 23. ACCEPTANCE CRITERIA CHO LISTENING

- real thumbnail / meaningful visual;
- synchronized transcript;
- word/sentence timing;
- replay line;
- speed control;
- tap word;
- meaning;
- pronunciation/pinyin;
- explanation;
- save word;
- shadowing;
- speaking;
- optional quiz;
- mixed source support;
- video/audio both supported.

---

# 24. ACCEPTANCE CRITERIA CHO WRITING

- intent/context visible before writing;
- clear editor;
- review explanation, không chỉ correction;
- natural alternatives;
- learner level aware;
- save useful expressions;
- no generic "AI assistant" visual language;
- support English + Chinese;
- focused layout.

---

# 25. ACCEPTANCE CRITERIA CHO MY LANGUAGE

Không được chỉ là vocabulary count dashboard.

Cần hướng đến:

- words;
- phrases;
- expressions;
- sentence patterns;
- grammar patterns;
- pronunciation;
- saved examples;
- mistakes worth remembering;
- review state;
- recall schedule.

Metrics có thể tồn tại nhưng không được chiếm vai trò chính.

---


# 25A. BEGINNER CLARITY ACCEPTANCE CRITERIA

Một flow/màn hình learner-facing không được duyệt nếu người mới hoàn toàn không biết bước tiếp theo là gì.

Bắt buộc kiểm tra:

- Một người chưa từng dùng Orena có thể chỉ ra primary action trong vài giây.
- Một learner bắt đầu từ số 0 không bị buộc phải hiểu Discover, world, intention, modality hoặc learning taxonomy.
- Navigation dùng từ quen thuộc khi clarity quan trọng.
- Không có learner-facing fantasy/lore bắt buộc.
- Không dùng slogan để thay thế instruction.
- Guided path có thể bắt đầu ngay.
- Explore không chặn hoặc làm lu mờ guided start.
- Beginner không bị ném trực tiếp vào content quá khó chỉ vì content đó đẹp.
- English và Chinese đều phải có beginner-safe entry.
- Mobile viewport đầu vẫn cho thấy rõ hành động bắt đầu/tiếp tục.

# 26. PROMPT GỢI Ý CHO AI/AGENT AUDIT & REWORK

Bạn có thể đưa nguyên prompt sau cho agent:

---

**ROLE**

Bạn đang audit và refactor Orena, một app học ngôn ngữ đã được rebuild với North Star rõ ràng.

Bạn KHÔNG được coi đây là task "làm giao diện đẹp hơn".

Bạn phải đánh giá architecture trải nghiệm, information hierarchy, content model, navigation, interaction và visual language theo DESIGN CONSTITUTION được cung cấp.

**NORTH STAR**

Orena không phải một bộ công cụ học ngôn ngữ.

Orena là một thế giới để người học bước vào, khám phá nội dung, con người, câu chuyện và ý tưởng; ngôn ngữ là phương tiện để họ hiểu và tham gia vào thế giới đó.

> Build a world worth entering, where language is something you live through—not a set of tools you operate.

**CORE RULE**

- Content-first
- Curiosity-first
- Human-intention-first
- Skills below experience
- AI backstage
- Focused learning once inside content
- Less words, more life
- Artwork is a system, not decoration
- One shared Art Bible across the product
- Clarity first, curiosity next, depth over time
- Simple front door, deep world behind it
- Guided path and exploration must coexist

**DO NOT**

- Chỉ thay CSS.
- Chỉ thêm animation.
- Chỉ thêm mascot.
- Chỉ thêm background illustration.
- Lặp pattern `eyebrow + giant header + slogan + paragraph + mascot` trên mọi trang.
- Viết nhiều copy để bù cho UI/artwork thiếu sức sống.
- Dùng artwork từ nhiều phong cách không đồng bộ.
- Dùng placeholder chữ cái / hình học làm visual production.
- Biến Orena thành fantasy UI.
- Xóa Reading/Listening chỉ vì chúng là skill.
- Nhân bản content cho từng skill.
- Tạo thêm taxonomy mới nếu chưa cần.
- Làm mất các chức năng hiện có.
- Làm regression English/Chinese.
- Thay đổi backend contract nếu không cần.
- Tự ý invent palette mới.
- Dùng generic SaaS cards cho mọi thứ.
- Biến `world` thành fantasy/lore hoặc metaphor learner bắt buộc phải hiểu.
- Đổi các navigation label rõ ràng thành câu poetic khó hiểu chỉ để tạo personality.
- Để learner mới hoàn toàn không có một primary action rõ ràng.

**AUDIT FIRST**

Trước khi code, hãy:

1. Audit từng màn hình hiện tại.
2. Map mỗi vấn đề vào Design Constitution.
3. Phân loại:
   - product architecture issue
   - information architecture issue
   - UX issue
   - visual system issue
   - content model issue
   - missing learning capability
4. Chỉ ra regression risk.
5. Đề xuất target architecture.
6. Nêu rõ phần nào giữ nguyên.
7. Nêu rõ phần nào cần refactor.
8. Nêu rõ phần nào không được động vào.

**FIRST IMPLEMENTATION TARGET**

Bắt đầu với Discover.

Mục tiêu:

- Discover không còn bị tổ chức chủ yếu theo Reading/Listening.
- Giữ horizontal content rail.
- Dùng content/topic/theme/mood/context để tạo discovery.
- Có mixed-content rails.
- Content imagery/title là entry point chính.
- Skill/type/level là secondary metadata.
- Không phá mobile behavior.
- Không phá continue/progress.
- Không phá English/Chinese.
- Không thêm decoration giả immersive.

**ORENA TEST**

Trước khi hoàn thành, hỏi:

> Nếu xóa các nhãn Reading / Listening / Speaking / Writing, màn hình này vẫn cho learner lý do để bước vào không?

Nếu không, thiết kế chưa đạt.

**OUTPUT REQUIRED BEFORE CODING**

- Current-state audit
- Problem map
- Proposed IA
- Proposed content model impact
- Proposed UI changes
- What stays unchanged
- Regression checklist
- Screens to update
- Acceptance criteria
- Implementation plan

Không code cho đến khi audit và plan được duyệt.

---

# 27. KẾT LUẬN

Orena hiện tại không thiếu các mảnh đúng.

Nó đang có:

- branding tốt;
- palette tốt;
- typography tốt;
- nhiều copy đúng chất;
- một số interaction direction đúng;
- rail layout tốt;
- content infrastructure bắt đầu hình thành;
- library concept;
- mascot;
- Daily Feed;
- Practice có human-intention direction.

Vấn đề lớn nhất là:

> **những mảnh đúng đang được ghép vào một architecture cũ.**

Mục tiêu tiếp theo không phải là "redesign Orena từ số 0".

Mục tiêu là:

> **khôi phục North Star, chỉnh lại information architecture và content hierarchy, sau đó để visual design phục vụ architecture đó.**

Nếu làm đúng, kế hoạch thêm nhiều:

- books;
- stories;
- articles;
- video;
- audio;

sẽ không làm Orena rối hơn.

Ngược lại, chính kho nội dung lớn sẽ giúp Orena trở thành một thế giới có đủ thứ để khám phá.

---

**END OF DOCUMENT**
