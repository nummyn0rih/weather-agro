import { Skeleton } from '@/components/ui/skeleton';

const APPLE_PASTELS: { label: string; bg: string; fg: string; dot: string }[] =
  [
    {
      label: 'blue',
      bg: 'bg-apple-blue-pastel',
      fg: 'text-apple-blue',
      dot: 'bg-apple-blue',
    },
    {
      label: 'green',
      bg: 'bg-apple-green-pastel',
      fg: 'text-apple-green',
      dot: 'bg-apple-green',
    },
    {
      label: 'orange',
      bg: 'bg-apple-orange-pastel',
      fg: 'text-apple-orange',
      dot: 'bg-apple-orange',
    },
    {
      label: 'red',
      bg: 'bg-apple-red-pastel',
      fg: 'text-apple-red',
      dot: 'bg-apple-red',
    },
    {
      label: 'yellow',
      bg: 'bg-apple-yellow-pastel',
      fg: 'text-apple-yellow',
      dot: 'bg-apple-yellow',
    },
    {
      label: 'purple',
      bg: 'bg-apple-purple-pastel',
      fg: 'text-apple-purple',
      dot: 'bg-apple-purple',
    },
    {
      label: 'pink',
      bg: 'bg-apple-pink-pastel',
      fg: 'text-apple-pink',
      dot: 'bg-apple-pink',
    },
    {
      label: 'teal',
      bg: 'bg-apple-teal-pastel',
      fg: 'text-apple-teal',
      dot: 'bg-apple-teal',
    },
    {
      label: 'indigo',
      bg: 'bg-apple-indigo-pastel',
      fg: 'text-apple-indigo',
      dot: 'bg-apple-indigo',
    },
  ];

const NOTION_CHIPS: { label: string; color: string }[] = [
  { label: 'Gray', color: 'gray' },
  { label: 'Brown', color: 'brown' },
  { label: 'Orange', color: 'orange' },
  { label: 'Yellow', color: 'yellow' },
  { label: 'Green', color: 'green' },
  { label: 'Blue', color: 'blue' },
  { label: 'Purple', color: 'purple' },
  { label: 'Pink', color: 'pink' },
  { label: 'Red', color: 'red' },
];

const APPLE_RADII = [
  { token: 'apple-sm', value: '10px', cls: 'rounded-apple-sm' },
  { token: 'apple-md', value: '16px', cls: 'rounded-apple-md' },
  { token: 'apple-lg', value: '20px', cls: 'rounded-apple-lg' },
  { token: 'apple-xl', value: '28px', cls: 'rounded-apple-xl' },
];

const APPLE_SHADOWS = [
  { token: 'apple-sm', cls: 'shadow-apple-sm' },
  { token: 'apple-md', cls: 'shadow-apple-md' },
  { token: 'apple-lg', cls: 'shadow-apple-lg' },
  { token: 'apple-xl', cls: 'shadow-apple-xl' },
] as const;

export function StyleguidePage() {
  return (
    <div className="flex flex-col gap-12 p-6 md:p-10">
      <header className="flex flex-col gap-2">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          dev-only
        </span>
        <h1 className="text-4xl font-bold tracking-tight">Styleguide</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Design tokens for Apple HIG (dashboard, charts, analytics) and
          Notion-style (tables, journal, settings, alerts) surfaces. Both
          systems support light and dark themes — toggle via the header switch.
        </p>
      </header>

      <Section title="Typography">
        <div className="flex flex-col gap-3">
          <div className="text-display-lg font-bold tracking-tight">
            Display Large · Inter 800
          </div>
          <div className="text-display-md font-bold tracking-tight">
            Display Medium · Inter 700
          </div>
          <div className="text-display-sm font-semibold tracking-tight">
            Display Small · Inter 600
          </div>
          <div className="text-2xl font-semibold tracking-tight">
            Heading 2xl · Inter 600
          </div>
          <div className="text-lg font-medium">Body Large · Inter 500</div>
          <div className="text-base">Body Base · Inter 400</div>
          <div className="text-sm text-muted-foreground">
            Caption · Inter 400 muted
          </div>
          <div className="notion-numeric font-mono text-sm">
            Mono / numeric · 1234.56 · JetBrains Mono
          </div>
        </div>
      </Section>

      <Section
        title="Apple HIG"
        subtitle="Large radii, soft layered shadows, system blue, pastel accents"
      >
        <div className="surface-apple flex flex-col gap-8 rounded-apple-lg p-6 md:p-8">
          <Subsection title="Accent — System Blue">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="rounded-apple-md bg-apple-blue px-5 py-2.5 text-sm font-medium text-white shadow-apple-sm transition-all duration-200 ease-apple hover:bg-apple-blue-hover hover:shadow-apple-md focus:outline-none focus-visible:ring-2 focus-visible:ring-apple-blue focus-visible:ring-offset-2 focus-visible:ring-offset-apple-bg"
              >
                Primary Action
              </button>
              <button
                type="button"
                className="hover:bg-apple-blue/15 rounded-apple-md bg-apple-blue-pastel px-5 py-2.5 text-sm font-medium text-apple-blue transition-all duration-200 ease-apple"
              >
                Secondary
              </button>
              <span className="rounded-apple-full bg-apple-surface px-4 py-1.5 text-xs font-medium text-apple-text-secondary shadow-apple-sm">
                Pill
              </span>
            </div>
          </Subsection>

          <Subsection title="Pastel palette">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
              {APPLE_PASTELS.map(({ label, bg, fg, dot }) => (
                <div
                  key={label}
                  className={`flex items-center justify-between rounded-apple-md ${bg} px-4 py-3 text-sm font-medium ${fg}`}
                >
                  <span className="capitalize">{label}</span>
                  <span className={`h-3 w-3 rounded-full ${dot}`} />
                </div>
              ))}
            </div>
          </Subsection>

          <Subsection title="Cards & shadows">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
              {APPLE_SHADOWS.map(({ token, cls }) => (
                <div
                  key={token}
                  className={`rounded-apple-lg bg-apple-surface p-5 ${cls} transition-shadow duration-300 ease-apple hover:shadow-apple-xl`}
                >
                  <div className="text-xs font-medium uppercase tracking-wide text-apple-text-tertiary">
                    shadow-{token}
                  </div>
                  <div className="mt-3 text-3xl font-bold tracking-tight text-apple-text">
                    24.7°
                  </div>
                  <div className="mt-1 text-sm text-apple-text-secondary">
                    Сочи · Сегодня
                  </div>
                </div>
              ))}
            </div>
          </Subsection>

          <Subsection title="Radii">
            <div className="flex flex-wrap gap-4">
              {APPLE_RADII.map(({ token, value, cls }) => (
                <div
                  key={token}
                  className={`flex h-24 w-24 flex-col items-center justify-center ${cls} bg-apple-blue-pastel text-apple-blue`}
                >
                  <span className="text-xs font-semibold">{token}</span>
                  <span className="text-xs text-apple-text-secondary">
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </Subsection>

          <Subsection title="Skeleton (Apple)">
            <div className="rounded-apple-lg bg-apple-surface p-5 shadow-apple-md">
              <Skeleton className="h-4 w-32 rounded-apple-sm bg-apple-bg" />
              <Skeleton className="mt-4 h-10 w-24 rounded-apple-sm bg-apple-bg" />
              <Skeleton className="mt-2 h-3 w-40 rounded-apple-sm bg-apple-bg" />
            </div>
          </Subsection>
        </div>
      </Section>

      <Section
        title="Notion-style"
        subtitle="Thin borders, dense layout, neutral hover, tabular numerics"
      >
        <div className="surface-notion overflow-hidden rounded-notion-md border border-notion-border">
          <div className="border-b border-notion-border px-5 py-3">
            <h3 className="text-sm font-semibold text-notion-text">
              Журнал событий
            </h3>
            <p className="text-xs text-notion-text-muted">
              Sticky header · hover rows · моноширинные числа
            </p>
          </div>

          <Subsection title="Filter chips" inset>
            <div className="flex flex-wrap gap-2">
              {NOTION_CHIPS.map(({ label, color }) => (
                <span
                  key={color}
                  className="inline-flex items-center gap-1.5 rounded-notion-sm px-2 py-0.5 text-xs font-medium"
                  style={{
                    backgroundColor: `var(--notion-chip-${color}-bg)`,
                    color: `var(--notion-chip-${color}-fg)`,
                  }}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      backgroundColor: `var(--notion-chip-${color}-fg)`,
                    }}
                  />
                  {label}
                </span>
              ))}
            </div>
          </Subsection>

          <Subsection title="Table" inset>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="sticky top-0 bg-notion-bg">
                  <tr className="border-b border-notion-border text-left text-xs font-medium uppercase tracking-wide text-notion-text-muted">
                    <th className="px-3 py-2">Дата</th>
                    <th className="px-3 py-2">Локация</th>
                    <th className="px-3 py-2 text-right">T мин, °C</th>
                    <th className="px-3 py-2 text-right">T макс, °C</th>
                    <th className="px-3 py-2 text-right">Осадки, мм</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['2026-05-10', 'Сочи', 14.2, 22.7, 0.0],
                    ['2026-05-11', 'Краснодар', 12.6, 24.1, 1.4],
                    ['2026-05-12', 'Ростов-на-Дону', 11.3, 23.5, 2.6],
                    ['2026-05-13', 'Воронеж', 9.1, 21.0, 0.0],
                  ].map((row) => (
                    <tr
                      key={row[0] as string}
                      className="border-b border-notion-border text-notion-text transition-colors hover:bg-notion-row-hover"
                    >
                      <td className="notion-numeric px-3 py-2 font-mono text-notion-text-muted">
                        {row[0]}
                      </td>
                      <td className="px-3 py-2">{row[1]}</td>
                      <td className="notion-numeric px-3 py-2 text-right font-mono">
                        {(row[2] as number).toFixed(1)}
                      </td>
                      <td className="notion-numeric px-3 py-2 text-right font-mono">
                        {(row[3] as number).toFixed(1)}
                      </td>
                      <td className="notion-numeric px-3 py-2 text-right font-mono">
                        {(row[4] as number).toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Subsection>

          <Subsection title="Skeleton (Notion)" inset>
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 border-b border-notion-border py-2 last:border-b-0"
                >
                  <Skeleton className="h-3 w-20 rounded-notion-sm bg-notion-surface-hover" />
                  <Skeleton className="h-3 w-32 rounded-notion-sm bg-notion-surface-hover" />
                  <Skeleton className="ml-auto h-3 w-16 rounded-notion-sm bg-notion-surface-hover" />
                </div>
              ))}
            </div>
          </Subsection>
        </div>
      </Section>

      <Section title="Spacing scale">
        <div className="flex items-end gap-2">
          {[1, 2, 3, 4, 5, 6, 8, 10, 12, 16].map((n) => (
            <div key={n} className="flex flex-col items-center gap-2">
              <div
                className="bg-apple-blue-pastel"
                style={{
                  width: `var(--space-${n})`,
                  height: `var(--space-${n})`,
                }}
              />
              <span className="text-xs text-muted-foreground">space-{n}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

interface SectionProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

function Section({ title, subtitle, children }: SectionProps) {
  return (
    <section className="flex flex-col gap-4">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        {subtitle && (
          <p className="text-sm text-muted-foreground">{subtitle}</p>
        )}
      </div>
      {children}
    </section>
  );
}

interface SubsectionProps {
  title: string;
  inset?: boolean;
  children: React.ReactNode;
}

function Subsection({ title, inset = false, children }: SubsectionProps) {
  return (
    <div className={inset ? 'px-5 py-4' : ''}>
      <div className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  );
}

export default StyleguidePage;
