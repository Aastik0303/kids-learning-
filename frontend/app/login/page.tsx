import Link from "next/link";
import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <div className="grid w-full gap-4">
        <AuthForm mode="login" />
        <Link className="text-center font-bold text-leaf" href="/signup">
          Create demo account
        </Link>
        <Link className="text-center font-bold text-ink/60" href="/forgot-password">
          Forgot your password?
        </Link>
      </div>
    </main>
  );
}
