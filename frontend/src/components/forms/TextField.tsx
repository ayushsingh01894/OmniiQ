import { forwardRef, useId, type InputHTMLAttributes } from "react";

type Props = { label: string; error?: string | undefined; hint?: string } & Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id"
>;

export const TextField = forwardRef<HTMLInputElement, Props>(function TextField(
  { label, error, hint, ...rest },
  ref,
) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ");
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        ref={ref}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className="w-full rounded-sm border border-line bg-surface px-3 py-2 text-sm aria-[invalid=true]:border-danger"
        {...rest}
      />
      {hint && !error ? (
        <p id={hintId} className="text-sm text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
});
