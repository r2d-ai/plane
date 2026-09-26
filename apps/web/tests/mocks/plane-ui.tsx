import type { ReactNode } from "react";

export function MockUiButton({
  children,
  onClick,
  disabled,
}: {
  children?: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

export function MockCustomSelect({ children }: { children?: ReactNode }) {
  return <div>{children}</div>;
}

export function MockCustomSelectOption({ children }: { children?: ReactNode }) {
  return <div>{children}</div>;
}

MockCustomSelect.Option = MockCustomSelectOption;
