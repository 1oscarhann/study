import { ComingSoon } from "../../components/ComingSoon";

export function SignupPage() {
  return (
    <main className="mx-auto max-w-lg px-4 py-10">
      <ComingSoon title="Sign up" phase={2}>
        Username, password and your year group. Nothing else.
      </ComingSoon>
    </main>
  );
}
