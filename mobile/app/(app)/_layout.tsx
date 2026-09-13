import {Redirect, Stack} from 'expo-router';
import {useSession} from '../../src/auth/SessionHarness';
import {useTheme} from '../../src/theme/ThemeProvider';


export default function AppLayout() {
  const {session} = useSession();
  const {tokens} = useTheme();
  if (session.status !== 'authenticated') return <Redirect href="/(auth)/sign-in" />;

  return (

      <Stack screenOptions={{headerShown: false, contentStyle: {backgroundColor: tokens.colors.background}}} />

  );
}
