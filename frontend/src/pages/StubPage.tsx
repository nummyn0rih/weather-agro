interface StubPageProps {
  title: string;
  description?: string;
}

export function StubPage({ title, description }: StubPageProps) {
  return (
    <div className="flex h-full flex-col p-6 md:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {description ?? 'Страница будет реализована в следующих задачах.'}
      </p>
    </div>
  );
}

export default StubPage;
