# Learnings

Mechanisms this project had to get right, written down once, in general terms, from the specific
episode that forced them.

It is the counterpart to `REVISIT.md`. That file holds what is committed and not yet understood;
this one holds what *is* understood and is worth carrying — the reasoning that would otherwise
survive only as a line of code whose motivation is invisible six weeks later. A subject moves from
one file to the other by being explained.

**Scope.** Every entry begins with something that happened in this tree: a command that was run, a
defect that was found, a decision that was taken. The generalisation at the end of an entry has to
be earned by that episode. This is not a syllabus and not a reading list — the phases are the
curriculum, and a separate learning track has been refused. An entry that could have been written
without this repo existing does not belong here.

**Convention.** Entries are `L<n>`, stable. Each states **what happened**, **the mechanism**, and
**the practice** that generalises. Entries are not struck through: unlike a defect or an open
question, a learning has no terminal state.

---

## L1 — File modes, and where a credential lives

### What happened

The ENTSO-E API key was kept at `secrets/secrets.yaml` inside the repo, read by path in
`ingest.py`, and protected by a `.gitignore` rule added after the file already existed. It was
mode `644`. Checking `git log --all -S` confirmed it had never been committed, so nothing needed
rotating; the design had simply been relying on luck.

It was migrated to `~/.config/forecaster/env`, mode `600` in a directory of mode `700`, and the
repo copy deleted. `config/config.yaml` names the variable — `source.entsoe.api_key_env:
ENTSOE_TOKEN` — and the code reads the value from the environment at the point of use.

### The mechanism: what 600 and 700 mean

A Unix file has three sets of permissions — **owner**, **group**, **everyone else** — and each set
is three bits: read (4), write (2), execute (1), summed into one octal digit. The leading `0` is
just octal notation.

```
600  ->  6 0 0  ->  rw- --- ---  ->  -rw-------
700  ->  7 0 0  ->  rwx --- ---  ->  drwx------
644  ->  6 4 4  ->  rw- r-- r--  ->  -rw-r--r--   (what the repo copy was)
```

So `600` is "the owner may read and write it; nobody else may do anything". `644` is the default
for a newly created file on most systems, and the last two digits are the problem: every other
account on the machine could read that key.

On a **directory** the bits mean something different, which is the part worth internalising:

- **read** on a directory means *list the names inside it*
- **execute** means *traverse it* — resolve a path through it to reach something inside
- so `700` is the directory equivalent of `600`: the owner can list and enter, nobody else can do
  either. A directory with `600` would be listable and useless, because nothing inside could be
  opened.

Two related mechanisms that matter in practice:

- **`umask`** subtracts bits from the mode a program requests at creation time. It is why files
  usually land at `644` rather than `666`.
- **Creating with the mode, rather than fixing it afterwards.** The migration used
  `os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)`, not "write the file, then `chmod` it". Between
  those two steps the file exists and is world-readable, and a secret written into that window has
  already been exposed. `O_EXCL` additionally makes the call fail rather than clobber an existing
  file.

### The mechanism: how the key reaches the code

Four steps, each of which can be checked independently:

1. **The config names the variable, and never holds the value.**
   `source.entsoe.api_key_env: ENTSOE_TOKEN`.
2. **The value lives in a file outside the tree**, `~/.config/forecaster/env`, as
   `ENTSOE_TOKEN=...`, mode `600`.
3. **A shell loads it into the environment.** `set -a` makes every subsequent assignment exported,
   so `set -a; . ~/.config/forecaster/env; set +a` turns the file's lines into environment
   variables and then stops the auto-export.
4. **The code reads it at the point of use**, `os.environ[cfg.source.entsoe.api_key_env]`, and
   passes it straight to the client. It never becomes a field on a config object.

Step 4 is the one carrying the weight here. `IngestResult` embeds a whole source-config object and
is destined for a persisted run history; MLflow logs params; logs print config. Had the key been a
config *field*, all three would contain it. Because config holds only the name, a full
`model_dump_json()` contains `'api_key_env': 'ENTSOE_TOKEN'` and nothing else.

### What an environment variable does not protect against

Worth stating, because "it's in an env var" gets treated as a conclusion:

- `/proc/<pid>/environ` exposes it to the same user, and to root.
- **Every child process inherits it.**
- Anything that dumps `os.environ`, interpolates it into a URL, or includes it in an exception
  message leaks it into logs.
- Exporting it by hand puts it in shell history — which is why it lives in a file that is sourced,
  not in a command that is typed.
- Loading it from a shell profile puts it in the environment of *every* process started on that
  machine. Loading it per-session keeps the blast radius to that shell and its children.

The property achieved is "not in the repo, not in any dump, not in any artifact" — not "safe from
someone with a shell on the box".

### The practice

1. **Config names secrets; it never contains them.** The indirection is what makes leaking one
   structurally impossible rather than a thing to remember.
2. **Secrets live outside the source tree.** A `.gitignore` rule is a mitigation, not a design —
   it protects a file that should not have been there.
3. **Create with the restrictive mode atomically**, never write-then-`chmod`.
4. **Read at the point of use.** A credential that never enters a long-lived object cannot be
   serialised out of one.
5. **Fail loudly, naming the variable and never the value**, when it is missing.
6. **Pick the one mechanism that exists in every environment.** A file at a fixed path exists on a
   laptop and nowhere else; systemd's `EnvironmentFile=`, a container's `--env` and a cluster's
   secret store all produce environment variables, so code that reads the environment moves
   without changes.
7. **"Never committed" is a claim to check, not to assume** — `git log --all -S'<fragment>'`. If it
   ever was committed, rewriting history does not recall the clones that already have it: rotate
   the credential instead.
