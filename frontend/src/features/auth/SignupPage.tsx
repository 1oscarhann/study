import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useFinishAuth, useSignup, useUsernameIdeas } from "../../api/auth";
import type { AuthWithRecoveryCode } from "../../api/types";
import { useGuestRedirect } from "../../components/guards";
import { Button } from "../../components/ui/Button";
import { FormError, PasswordField, SelectField, TextField } from "../../components/ui/Field";
import { YearGroupOptions } from "../../components/ui/YearGroupOptions";
import { AuthLayout } from "./AuthLayout";
import { formErrors } from "./formErrors";
import { RecoveryCodeCard } from "./RecoveryCodeCard";

/** July and August: students are between years, so say which one to pick. */
export function isSummerHoliday(today = new Date()): boolean {
  const month = today.getMonth(); // 0 = Jan
  return month === 6 || month === 7;
}

export function SignupPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [yearGroup, setYearGroup] = useState("");
  const [done, setDone] = useState<AuthWithRecoveryCode | null>(null);
  const signup = useSignup();
  const ideas = useUsernameIdeas();
  const finishAuth = useFinishAuth();
  const navigate = useNavigate();
  const redirect = useGuestRedirect(done !== null);
  const errors = formErrors(signup.error, ["username", "password", "year_group"] as const);

  function submit(e: FormEvent) {
    e.preventDefault();
    signup.mutate(
      { username: username.trim(), password, year_group: Number(yearGroup) },
      { onSuccess: setDone },
    );
  }

  if (redirect) return redirect;

  if (done) {
    return (
      <AuthLayout title={`You're in, ${done.user.username}!`}>
        <RecoveryCodeCard
          code={done.recovery_code}
          doneLabel="Start revising"
          onDone={() => {
            finishAuth(done.user);
            navigate("/", { replace: true });
          }}
        />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Create your account" subtitle="Takes 20 seconds. No email needed.">
      <form onSubmit={submit} className="space-y-5" noValidate>
        <div className="space-y-2">
          <TextField
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            maxLength={20}
            required
            hint="Don't use your real name. Your username shows on leaderboards."
            error={errors.field("username")}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="ghost" className="!min-h-9 !px-0 text-sm" loading={ideas.isPending} onClick={() => ideas.mutate()}>
              Suggest a username
            </Button>
            {ideas.data?.ideas.map((idea) => (
              <button
                key={idea}
                type="button"
                onClick={() => setUsername(idea)}
                className="rounded-full border border-[var(--line)] px-3 py-1.5 text-sm font-medium hover:border-brand-500"
              >
                {idea}
              </button>
            ))}
          </div>
        </div>
        <PasswordField
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          required
          hint="At least 8 characters. A short phrase like “purple tiger runs fast” works well."
          error={errors.field("password")}
        />
        <SelectField
          label="Year group"
          value={yearGroup}
          onChange={(e) => setYearGroup(e.target.value)}
          required
          hint={
            isSummerHoliday()
              ? "It's the summer holidays, so pick the year you've just finished. You'll move up automatically on 1 September."
              : "You'll move up automatically every September."
          }
          error={errors.field("year_group")}
        >
          <YearGroupOptions placeholder="Choose your year" />
        </SelectField>
        <FormError message={errors.general} />
        <Button type="submit" block loading={signup.isPending} disabled={!username || !password || !yearGroup}>
          Create account
        </Button>
        <p className="text-center text-xs text-muted">
          We only store your username, your password (scrambled) and your year group. No email, no real name.
        </p>
      </form>
      <p className="mt-5 text-center text-sm">
        Already have an account?{" "}
        <Link to="/login" className="font-semibold text-brand-600 dark:text-brand-400">
          Log in
        </Link>
      </p>
    </AuthLayout>
  );
}
