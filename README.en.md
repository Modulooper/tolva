# Tolva

> *Tolva* (Spanish): the hopper — the mouth through which material enters a machine.

**Where your data goes in, and it talks back.** You tell it what you're
getting; it asks what it can't infer — that month column reading `03`, is that
text or a number? — and it only writes once you say yes.

Almost every AI data tool has gone after analysis, the end of the pipeline that
already had tooling. This one is about the start: **ingestion**.

With one rule that isn't negotiable: **the AI is in the design, not in the
execution.** The conversation produces a config file; from then on it's plain
SQL running on its own, identically every month. **No model ever touches a row
of your data.**

Local, single-user, self-contained, on DuckDB. No server, no auth, no cloud.
Everything lives in one file on your disk.

> **A note on language.** The documentation, the CLI verbs and the config keys
> are in Spanish. This matters less than it looks: you don't write the config,
> you talk and it gets written for you — and the assistant reads Spanish and
> answers you in English. Your own table and column names are entirely free, so
> `date` and `fecha` work exactly the same. This page is the short version; the
> full documentation is [README.md](README.md), in Spanish.

## The problem

Almost everyone has work data that doesn't fit in a tool and doesn't deserve
one: the expenses spreadsheet, the bank statement you download every month, the
list of open items, the ERP export you open and cross-reference by hand.
Setting up a database for that costs more than it saves, so nobody does — and
you end up with three names for the same thing spread across five files.

Tolva assumes modelling is a conversation, and that the expensive part isn't
writing the `CREATE TABLE` but deciding what goes in it.

## What it looks like

```
> I want to track the tasks I have open

`idea` already exists, and three of its rows are tasks: "Publish the project
on GitHub", "Come up with a name". Analysis says `estado` matches
`idea.estado`, and `cliente` overlaps 1.0 with the `cliente` table, so it
goes in as a foreign key rather than free text.

Are they the same thing, or is an idea what you'd like to do and a task what
you have to do?

> the second one. and I want to log the hours it took when I close it

Proposal: a `tarea` table with a due date, a close date and actual hours.
Two decisions I need you to confirm...
```

Out of that comes a migration, a catalogue entry, and a row in `_decisiones`
recording *why* — so that in six months the reason is still there.

## What it does under the hood

- **Nothing is created blind.** Before a new table, overlap is checked against
  the semantic catalogue *and* against the real data, with measured evidence
  rather than judgement.
- **When loading, what matters is what each file replaces.** You declare it
  once (`campos_singularidad`), and re-uploading the corrected report replaces
  the right slice instead of duplicating it.
- **Business rules that stop the load.** A `SELECT` that aborts the load if it
  returns rows, or just warns. The same invariants govern the CRUD.
- **Everything leaves a trail, and the source file is kept.** From any row you
  can reach the file that brought it, and the receipts attached later.
- **Backups in parquet**, with grandfather-father-son retention and a recovery
  procedure that has been rehearsed end to end, not just documented.
- **Three layers separated by directory**: the framework, an example domain to
  play with, and yours — which never leaves your machine.

## Try it in two minutes

**You don't need to know Python.** Open an empty folder with
[Claude Code](https://claude.com/claude-code) and ask in your own words:

```
> clone <repo-url>, install it and show me the example
```

It handles the mechanical part — environment, dependencies, migrations — and
asks you the one thing it can't decide for you: where your data should live,
and whether you want backups. It ends by running a real load end to end —
file, transformation, a rule that fires on purpose, and an xlsx output — over
an example domain: an invented bookshop, with dummy data.

Your own installation starts empty: the core **creates no business tables at
all**.

From there on there's no installation, just conversation: tell it what you
want to track. The skills that steer that part (`definir-carga`,
`crear-proceso`) ship with the repository and are what the project is really
about: they profile the file, check overlap against the semantic catalogue and
propose a schema before touching anything.

### Or from the console

Requirements: Python 3.11+ and Git.

```bash
git clone <repo-url>
cd tolva
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

python -m motor.cli db migrar --con-ejemplos
python -m motor.cli registro listar demo_venta
python -m motor.cli etl ejecutar demo_ventas
```

On Windows PowerShell use `.venv\Scripts\Activate.ps1`; on macOS/Linux,
`source .venv/bin/activate`.

## Where your data lives

Four separately configurable locations, because their requirements are
opposites: the **store** must stay out of a synced folder (a database file is
not a document, and OneDrive or Dropbox will happily copy it mid-write);
**exports** usually want to be in one, since that's the point of generating
them; and **backups** want to be synced *and* far from the store.

```bash
python -m motor.cli db rutas    # where everything is, and why
```

## Issues and contributions

Open an **issue** — deliberately not email, so the answer stays public for the
next person with the same question. Issues in English are welcome.

Before a pull request, the suite must pass:

```bash
python -m unittest discover -s pruebas -t .
```

**Security**: if you find a vulnerability, don't open a public issue. Write to
modulooper@gmail.com and we'll coordinate a fix before disclosure.

## License

[MIT](LICENSE).
