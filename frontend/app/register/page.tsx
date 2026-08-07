import Link from "next/link";
import { AuthForm } from "@/components/auth/AuthForm";

export default function RegisterPage() {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <div className="grid w-full gap-4">
        <AuthForm mode="register" />
        <Link className="text-center font-bold text-leaf" href="/login">
          I already have a demo account
        </Link>
      </div>
    </main>
  );
}
