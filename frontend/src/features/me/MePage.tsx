import { useState, type FormEvent, type ReactNode } from "react";
import { useNavigate } from "react-router";

import {
  useChangePassword,
  useChangeYearGroup,
  useDeleteAccount,
  useLogout,
  useMe,
  useNewRecoveryCode,
} from "../../api/auth";
import type { Me } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { FormError, PasswordField, SelectField } from "../../components/ui/Field";
import { YearGroupOptions } from "../../components/ui/YearGroupOptions";
import { formErrors } from "../auth/formErrors";
import { RecoveryCodeCard } from "../auth/RecoveryCodeCard";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card space-y-4 p-5" aria-labelledby={title}>
      <h2 id={title} className="text-lg font-bold tracking-tight">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Success({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">
      {children}
    </p>
  );
}

function YearGroupSection({ me }: { me: Me }) {
  const [year, setYear] = useState(String(me.year_group ?? ""));
  const change = useChangeYearGroup();
  const errors = formErrors(change.error, ["year_group"] as const);
  const changed = year !== String(me.year_group ?? "");

  if (!me.can_change_year_group) {
    return (
      <Section title="Year group">
        <p>
          You're in <strong>{me.graduated ? "no year (graduated)" : `Year ${me.year_group}`}</strong>.
        </p>
        <p className="text-sm text-muted">
          You've already changed your year group this school year. You can change it again from 1 September.
        </p>
      </Section>
    );
  }

  return (
    <Section title="Year group">
      <p className="text-sm text-muted">
        You move up automatically every September. Only change this if it's wrong. You can change it{" "}
        <strong>once per school year</strong>.
      </p>
      <form
        className="space-y-3"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          change.mutate(Number(year));
        }}
      >
        <SelectField label="Your year group" value={year} onChange={(e) => setYear(e.target.value)} error={errors.field("year_group")}>
          <YearGroupOptions placeholder={me.graduated ? "Graduated" : undefined} />
        </SelectField>
        <FormError message={errors.general} />
        {changed && (
          <Button type="submit" loading={change.isPending}>
            Change to Year {year}
          </Button>
        )}
      </form>
    </Section>
  );
}

function PasswordSection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const change = useChangePassword();
  const errors = formErrors(change.error, ["current_password", "new_password"] as const);

  return (
    <Section title="Password">
      <form
        className="space-y-3"
        noValidate
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          change.mutate(
            { current_password: current, new_password: next },
            {
              onSuccess: () => {
                setCurrent("");
                setNext("");
              },
            },
          );
        }}
      >
        <PasswordField
          label="Current password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          autoComplete="current-password"
          error={errors.field("current_password")}
        />
        <PasswordField
          label="New password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          autoComplete="new-password"
          hint="At least 8 characters. This logs you out on your other devices."
          error={errors.field("new_password")}
        />
        <FormError message={errors.general} />
        {change.isSuccess && <Success>Password changed.</Success>}
        <Button type="submit" variant="secondary" loading={change.isPending} disabled={!current || !next}>
          Change password
        </Button>
      </form>
    </Section>
  );
}

function RecoveryCodeSection() {
  const [password, setPassword] = useState("");
  const newCode = useNewRecoveryCode();
  const errors = formErrors(newCode.error, ["password"] as const);

  if (newCode.data) {
    return (
      <Section title="Recovery code">
        <RecoveryCodeCard code={newCode.data.recovery_code} doneLabel="Done" onDone={() => newCode.reset()} />
      </Section>
    );
  }

  return (
    <Section title="Recovery code">
      <p className="text-sm text-muted">
        Lost your recovery code? Make a new one. Your old code will stop working.
      </p>
      <form
        className="space-y-3"
        noValidate
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          newCode.mutate(password, { onSuccess: () => setPassword("") });
        }}
      >
        <PasswordField
          label="Your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          error={errors.field("password")}
        />
        <FormError message={errors.general} />
        <Button type="submit" variant="secondary" loading={newCode.isPending} disabled={!password}>
          Make a new recovery code
        </Button>
      </form>
    </Section>
  );
}

function DeleteAccountSection() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const del = useDeleteAccount();
  const navigate = useNavigate();
  const errors = formErrors(del.error, ["password"] as const);

  return (
    <section className="space-y-4 rounded-2xl border border-rose-300 p-5 dark:border-rose-500/40" aria-labelledby="delete-account">
      <h2 id="delete-account" className="text-lg font-bold tracking-tight text-rose-700 dark:text-rose-400">
        Delete account
      </h2>
      {!open ? (
        <Button variant="secondary" onClick={() => setOpen(true)}>
          Delete my account…
        </Button>
      ) : (
        <form
          className="space-y-3"
          noValidate
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            del.mutate(password, { onSuccess: () => navigate("/login", { replace: true }) });
          }}
        >
          <p className="text-sm">
            This permanently deletes your account, progress, XP and sets. <strong>It can't be undone.</strong>
          </p>
          <PasswordField
            label="Type your password to confirm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            error={errors.field("password")}
          />
          <FormError message={errors.general} />
          <div className="flex flex-wrap gap-3">
            <Button type="submit" variant="danger" loading={del.isPending} disabled={!password}>
              Delete forever
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

export function MePage() {
  const { data: me } = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  if (!me) return null; // RequireAuth guarantees a user; this keeps TypeScript happy

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-4">
        <span
          className="grid size-16 shrink-0 place-items-center rounded-2xl bg-brand-600 text-2xl font-bold text-white"
          aria-hidden="true"
        >
          {me.username.slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-bold tracking-tight">{me.username}</h1>
          <p className="text-muted">
            {me.graduated ? "Graduated · not on leaderboards" : `Year ${me.year_group}`} · {me.total_xp} XP
          </p>
        </div>
      </header>

      <YearGroupSection key={`${me.year_group}-${me.can_change_year_group}`} me={me} />
      <PasswordSection />
      <RecoveryCodeSection />

      <Button
        variant="secondary"
        block
        loading={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSettled: () => navigate("/login", { replace: true }) })}
      >
        Log out
      </Button>

      <DeleteAccountSection />
    </div>
  );
}
