import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useFinishAuth, useRecover } from "../../api/auth";
import type { AuthWithRecoveryCode } from "../../api/types";
import { useGuestRedirect } from "../../components/guards";
import { Button } from "../../components/ui/Button";
import { FormError, PasswordField, TextField } from "../../components/ui/Field";
import { AuthLayout } from "./AuthLayout";
import { formErrors } from "./formErrors";
import { RecoveryCodeCard } from "./RecoveryCodeCard";

export function RecoverPage() {
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState<AuthWithRecoveryCode | null>(null);
  const recover = useRecover();
  const finishAuth = useFinishAuth();
  const navigate = useNavigate();
  const redirect = useGuestRedirect(done !== null);
  const errors = formErrors(recover.error, ["username", "recovery_code", "new_password"] as const);

  function submit(e: FormEvent) {
    e.preventDefault();
    recover.mutate(
      { username: username.trim(), recovery_code: code, new_password: password },
      { onSuccess: setDone },
    );
  }

  if (redirect) return redirect;

  if (done) {
    return (
      <AuthLayout title="Password reset" subtitle="Your old recovery code has stopped working. Here's your new one.">
        <RecoveryCodeCard
          code={done.recovery_code}
          onDone={() => {
            finishAuth(done.user);
            navigate("/", { replace: true });
          }}
        />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Reset your password" subtitle="Use the recovery code you saved when you signed up.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <TextField
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          error={errors.field("username")}
        />
        <TextField
          label="Recovery code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="ABCD-EFGH-JKMN-PQRS"
          autoComplete="off"
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
          className="font-mono"
          error={errors.field("recovery_code")}
        />
        <PasswordField
          label="New password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
          hint="At least 8 characters."
          error={errors.field("new_password")}
        />
        <FormError message={errors.general} />
        <Button type="submit" block loading={recover.isPending} disabled={!username || !code || !password}>
          Reset password
        </Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted">
        Lost your recovery code too? Sadly there's no other way back in, because we don't store emails. You can{" "}
        <Link to="/signup" className="font-semibold text-brand-600 dark:text-brand-400">
          make a new account
        </Link>
        .
      </p>
    </AuthLayout>
  );
}
