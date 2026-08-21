export function Button({ children }: { children: string }) {
  return <button className="rounded-md bg-brand px-4 py-2 text-white">{children}</button>;
}
