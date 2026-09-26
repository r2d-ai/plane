import type { ReactNode } from "react";

type LinkProps = {
  href: string;
  children?: ReactNode;
};

export default function Link({ href, children }: LinkProps) {
  return <a href={href}>{children}</a>;
}
