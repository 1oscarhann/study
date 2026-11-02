import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { useLogin } from "../../api/auth";
import { Button } from "../../components/ui/Button";
import { FormError, PasswordField, TextField } from "../../components/ui/Field";
import { AuthLayout } from "./AuthLayout";
import { formErrors } from "./formErrors";
import { safeNext } from "./safeNext";

export function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const errors = formErrors(login.error, ["username", "password"] as const);

  function submit(e: FormEvent) {
    e.preventDefault();
    login.mutate(
      { username: username.trim(), password },
      { onSuccess: () => navigate(safeNext(params.get("next")), { replace: true }) },
    );
  }

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to keep your streak going.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        <TextField
          label="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          required
          error={errors.field("username")}
        />
        <PasswordField
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
          error={errors.field("password")}
        />
        <FormError message={errors.general} />
        <Button type="submit" block loading={login.isPending} disabled={!username || !password}>
          Log in
        </Button>
      </form>
      <div className="mt-5 space-y-2 text-center text-sm">
        <p>
          New here?{" "}
          <Link to="/signup" className="font-semibold text-brand-600 dark:text-brand-400">
            Create an account
          </Link>
        </p>
        <p>
          Forgot your password?{" "}
          <Link to="/recover" className="font-semibold text-brand-600 dark:text-brand-400">
            Use your recovery code
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}
