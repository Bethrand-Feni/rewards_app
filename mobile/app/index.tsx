import { Redirect } from "expo-router";

import { useAuth } from "@/AuthContext";
import { Loading, Screen } from "@/components";

export default function Index() {
  const { loading, user } = useAuth();
  if (loading)
    return (
      <Screen scroll={false}>
        <Loading />
      </Screen>
    );
  if (!user) return <Redirect href="/auth" />;
  if (!user.family_id || !user.role) return <Redirect href="/onboarding" />;
  return <Redirect href={user.role === "PARENT" ? "/parent" : "/child"} />;
}
