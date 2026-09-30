import { LogOut } from 'lucide-react';
import { Button } from '../../../components/ui/Button';
import { useLogout, type Role } from '../api';

export function AccountPanel({ role }: { role: Role }) {
  const logout = useLogout();
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm text-text-muted">Signed in as {role}</span>
        <Button
          variant="ghost"
          icon={<LogOut aria-hidden="true" className="size-4" />}
          loading={logout.isPending}
          onClick={() => logout.mutate()}
        >
          Log out
        </Button>
      </div>
      {logout.isError && (
        <p role="alert" className="text-sm text-error">
          Couldn&apos;t log out. Check your connection and try again.
        </p>
      )}
    </div>
  );
}
