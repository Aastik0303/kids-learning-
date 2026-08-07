import Link from "next/link";

type Props = {
  href?: string;
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "berry" | "leaf" | "sky" | "sun";
};

const tones = {
  berry: "bg-berry text-white",
  leaf: "bg-leaf text-white",
  sky: "bg-sky text-white",
  sun: "bg-sunshine text-ink"
};

export function LargeButton({ href, children, onClick, disabled, tone = "leaf" }: Props) {
  const className = `inline-flex min-h-16 w-full items-center justify-center rounded-3xl px-6 py-4 text-center text-xl font-black shadow-soft transition hover:scale-[1.01] ${tones[tone]} ${disabled ? "opacity-50" : ""}`;
  if (href && !disabled) {
    return (
      <Link className={className} href={href}>
        {children}
      </Link>
    );
  }
  return (
    <button className={className} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}
