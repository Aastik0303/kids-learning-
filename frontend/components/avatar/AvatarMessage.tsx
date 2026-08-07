"use client";

export function AvatarMessage({ message }: { message: string }) {
  return (
    <div className="avatar-message" role="status" aria-live="polite">
      {message}
    </div>
  );
}
