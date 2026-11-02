import { Link } from "react-router";

export function NotFound() {
  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-bold tracking-tight">Page not found</h1>
      <Link to="/" className="font-medium text-brand-600 underline underline-offset-4">
        Back to home
      </Link>
    </section>
  );
}
