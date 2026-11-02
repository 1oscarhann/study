import { useMe } from "../../api/auth";
import { ApiStatus } from "./ApiStatus";

export function HomePage() {
  const { data: me } = useMe();
  return (
    <section className="space-y-4">
      <h1 className="text-2xl font-bold tracking-tight">Hey {me?.username}, ready to revise?</h1>
      <div className="card space-y-3 p-5">
        <p className="text-muted">
          Your avatar, streak, quick-launch topics, due reviews and exam countdowns will live here.
        </p>
        <ApiStatus />
      </div>
    </section>
  );
}
