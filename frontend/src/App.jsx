export default function App() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 px-8 py-6">
        <h1 className="text-3xl font-bold tracking-tight">CeremonyGuard</h1>
        <p className="mt-1 text-slate-400">
          Multi-Party Ceremony Consistency System
        </p>
      </header>

      <main className="flex-1 px-8 py-10">
        <section className="max-w-2xl rounded-lg border border-slate-800 bg-slate-900 p-6">
          <h2 className="text-lg font-semibold text-slate-200">Status</h2>
          <p className="mt-2 text-slate-400">
            Backend connection pending
          </p>
        </section>
      </main>

      <footer className="border-t border-slate-800 px-8 py-4 text-sm text-slate-500">
        Phase 1 &middot; Project Foundation
      </footer>
    </div>
  );
}
