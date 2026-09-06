import {useState} from 'react';
import {Linking, Pressable, ScrollView, StyleSheet, Text} from 'react-native';
import {configuredApiBaseUrl} from '../../src/api/config';
import {useI18n} from '../../src/i18n/I18nProvider';
import {useSession} from '../../src/auth/SessionHarness';
/** Review entry; no embedded historical learner product or second engine. */
export default function ExperienceReviewEntry() {
  const {locale} = useI18n();
  const {signOut} = useSession();
  const [error, setError] = useState(false);
  const zh = locale === 'zh';
  const open = async () => {
    try { await Linking.openURL(configuredApiBaseUrl() + '/#/'); }
    catch { setError(true); }
  };
  return <ScrollView contentContainerStyle={styles.page}>
    <Text style={styles.brand}>orena</Text>
    <Text accessibilityRole="header" style={styles.title}>{zh ? '一个值得走进去的世界。' : 'A world worth entering.'}</Text>
    <Text style={styles.copy}>{zh ? '新的 Orena 体验正在网页端接受评审。探索内容、主动练习，或带上你在意的语言。' : 'The new Orena experience is in web review. Discover something, practice with intention, or bring language you care about.'}</Text>
    <Pressable accessibilityRole="button" onPress={open} style={styles.button}><Text style={styles.action}>{zh ? '打开 Orena 网页体验' : 'Open Orena on the web'}</Text></Pressable>
    <Text style={styles.copy}>{zh ? '原生体验将在产品方向评审后继续建设。浏览器可能需要单独登录。' : 'The native experience will continue after product review. The browser may require a separate sign-in.'}</Text>
    {error && <Text accessibilityRole="alert" style={styles.copy}>{zh ? '无法打开配置的网页地址。' : 'The configured web address could not open.'}</Text>}
    <Pressable accessibilityRole="button" onPress={signOut}><Text style={styles.copy}>{zh ? '退出登录' : 'Sign out'}</Text></Pressable>
  </ScrollView>;
}
const styles = StyleSheet.create({page: {flexGrow: 1, backgroundColor: '#f6f2e8', padding: 28, paddingTop: 64, gap: 24}, brand: {fontSize: 28, fontWeight: '800', color: '#263d36'}, title: {fontSize: 38, lineHeight: 48, fontWeight: '700', color: '#263d36'}, copy: {fontSize: 17, lineHeight: 28, color: '#42554a'}, button: {backgroundColor: '#c54e36', padding: 18, borderRadius: 10}, action: {color: '#fffaf0', fontSize: 17, fontWeight: '700'}});
