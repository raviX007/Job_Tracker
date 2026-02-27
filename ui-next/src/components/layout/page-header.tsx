interface PageHeaderProps {
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export function PageHeader({ title, subtitle, children }: PageHeaderProps) {
  return (
    <div className="mb-6 flex items-start justify-between">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}

interface SectionHeaderProps {
  title: string;
}

export function SectionHeader({ title }: SectionHeaderProps) {
  return (
    <h2 className="mb-4 mt-8 text-lg font-semibold text-primary">
      {title}
    </h2>
  );
}
