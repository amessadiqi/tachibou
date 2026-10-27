import { useState, type FormEvent, type ReactElement } from "react";
import type { Automation, AutomationInput, FieldError, FileType } from "../api";
import { ApiError } from "../api";

type DraftReference = {
  key: string;
  file_type: FileType;
  file_path: string;
  label: string;
};

const FILE_GROUPS: { fileType: FileType; title: string; addLabel: string }[] = [
  { fileType: "configuration", title: "Configuration files", addLabel: "Add configuration file" },
  { fileType: "documentation", title: "Documentation", addLabel: "Add documentation" },
  { fileType: "log", title: "Log files", addLabel: "Add log file" },
];

export function AutomationForm({
  initial,
  submitLabel,
  onSubmit,
}: {
  initial?: Automation;
  submitLabel: string;
  onSubmit: (input: AutomationInput) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [owner, setOwner] = useState(initial?.owner ?? "");
  const [version, setVersion] = useState(initial?.version ?? "");
  const [executable, setExecutable] = useState(initial?.executable ?? "");
  const [argumentsText, setArgumentsText] = useState(initial?.arguments.join("\n") ?? "");
  const [workingDirectory, setWorkingDirectory] = useState(initial?.working_directory ?? "");
  const [entryPoint, setEntryPoint] = useState(initial?.entry_point ?? "");
  const [references, setReferences] = useState<DraftReference[]>(() =>
    (initial?.file_references ?? []).map((reference) => ({
      key: reference.id,
      file_type: reference.file_type,
      file_path: reference.file_path,
      label: reference.label ?? "",
    })),
  );
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    if (!name.trim()) {
      nextErrors.name = "Enter a name.";
    }
    if (!executable.trim()) {
      nextErrors.executable = "Enter an executable.";
    }
    if (!workingDirectory.trim()) {
      nextErrors.working_directory = "Enter a working directory.";
    }
    references.forEach((reference, index) => {
      if (!reference.file_path.trim()) {
        nextErrors[`file_references.${index}.file_path`] = "Enter a file path.";
      }
    });
    setFieldErrors(nextErrors);
    setFormError(null);
    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setSaving(true);
    try {
      await onSubmit({
        name: name.trim(),
        description: blankToNull(description),
        owner: blankToNull(owner),
        version: blankToNull(version),
        executable: executable.trim(),
        arguments: argumentsText
          .split("\n")
          .map((line) => line.trim())
          .filter((line) => line.length > 0),
        working_directory: workingDirectory.trim(),
        entry_point: blankToNull(entryPoint),
        file_references: references
          .filter((reference) => reference.file_path.trim())
          .map((reference) => ({
            file_type: reference.file_type,
            file_path: reference.file_path.trim(),
            label: blankToNull(reference.label),
          })),
      });
    } catch (caught: unknown) {
      if (caught instanceof ApiError) {
        setFormError(caught.message);
        setFieldErrors(Object.fromEntries(caught.errors.map((error: FieldError) => [error.field, error.message])));
      } else {
        setFormError("Tâchibou cannot reach the local service. Start it with tachibou start, then reload this page.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="space-y-8" onSubmit={handleSubmit} noValidate>
      {formError ? (
        <p role="alert" className="rounded-xl border border-clay/30 bg-white px-4 py-3 text-clay">
          {formError}
        </p>
      ) : null}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">About this automation</h2>
        <Field label="Name" error={fieldErrors.name}>
          <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Field label="Description" error={fieldErrors.description}>
          <textarea className={inputClass} rows={3} value={description} onChange={(event) => setDescription(event.target.value)} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Owner" error={fieldErrors.owner}>
            <input className={inputClass} value={owner} onChange={(event) => setOwner(event.target.value)} />
          </Field>
          <Field label="Version" error={fieldErrors.version}>
            <input className={inputClass} value={version} onChange={(event) => setVersion(event.target.value)} />
          </Field>
        </div>
      </section>
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">How it runs</h2>
        <Field
          label="Executable"
          hint="Absolute path, such as a virtual environment interpreter, or a command on PATH."
          error={fieldErrors.executable}
        >
          <input className={inputClass} value={executable} onChange={(event) => setExecutable(event.target.value)} />
        </Field>
        <Field label="Arguments" hint="One argument per line." error={fieldErrors.arguments}>
          <textarea className={`${inputClass} font-mono`} rows={4} value={argumentsText} onChange={(event) => setArgumentsText(event.target.value)} />
        </Field>
        <Field
          label="Working directory"
          hint="Absolute path to the folder the command starts in."
          error={fieldErrors.working_directory}
        >
          <input className={inputClass} value={workingDirectory} onChange={(event) => setWorkingDirectory(event.target.value)} />
        </Field>
        <Field
          label="Entry point"
          hint="Optional path to the main script. Tâchibou does not modify it."
          error={fieldErrors.entry_point}
        >
          <input className={inputClass} value={entryPoint} onChange={(event) => setEntryPoint(event.target.value)} />
        </Field>
      </section>
      <section className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold">Related files</h2>
          <p className="mt-1 text-sm text-ink/70">Optional paths to files that already exist. Tâchibou only remembers the path.</p>
        </div>
        {FILE_GROUPS.map((group) => (
          <FileGroup
            key={group.fileType}
            title={group.title}
            addLabel={group.addLabel}
            references={references.filter((reference) => reference.file_type === group.fileType)}
            onAdd={() =>
              setReferences((current) => [
                ...current,
                { key: crypto.randomUUID(), file_type: group.fileType, file_path: "", label: "" },
              ])
            }
            onChange={(key, patch) =>
              setReferences((current) =>
                current.map((reference) => (reference.key === key ? { ...reference, ...patch } : reference)),
              )
            }
            onRemove={(key) => setReferences((current) => current.filter((reference) => reference.key !== key))}
            errorFor={(key) => {
              const index = references.findIndex((reference) => reference.key === key);
              return fieldErrors[`file_references.${index}.file_path`];
            }}
          />
        ))}
      </section>
      <button className="rounded-lg bg-moss px-4 py-2 font-medium text-white disabled:opacity-60" type="submit" disabled={saving}>
        {saving ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}

function FileGroup({
  title,
  addLabel,
  references,
  onAdd,
  onChange,
  onRemove,
  errorFor,
}: {
  title: string;
  addLabel: string;
  references: DraftReference[];
  onAdd: () => void;
  onChange: (key: string, patch: Partial<DraftReference>) => void;
  onRemove: (key: string) => void;
  errorFor: (key: string) => string | undefined;
}) {
  return (
    <fieldset className="space-y-3">
      <legend className="text-sm font-medium">{title}</legend>
      {references.map((reference) => {
        const error = errorFor(reference.key);
        return (
          <div key={reference.key} className="grid gap-3 rounded-xl border border-line bg-white p-3 sm:grid-cols-[1fr_12rem_auto]">
            <label className="block text-sm">
              <span className="text-ink/70">Path</span>
              <input
                className={inputClass}
                value={reference.file_path}
                onChange={(event) => onChange(reference.key, { file_path: event.target.value })}
              />
              {error ? <span className="mt-1 block text-clay">{error}</span> : null}
            </label>
            <label className="block text-sm">
              <span className="text-ink/70">Label</span>
              <input
                className={inputClass}
                value={reference.label}
                onChange={(event) => onChange(reference.key, { label: event.target.value })}
              />
            </label>
            <button className="self-end rounded-lg border border-line px-3 py-2 text-sm" type="button" onClick={() => onRemove(reference.key)}>
              Remove
            </button>
          </div>
        );
      })}
      <button className="rounded-lg border border-line px-3 py-2 text-sm" type="button" onClick={onAdd}>
        {addLabel}
      </button>
    </fieldset>
  );
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactElement;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint ? <span className="mt-1 block text-sm text-ink/60">{hint}</span> : null}
      {error ? <span className="mt-1 block text-sm text-clay">{error}</span> : null}
    </label>
  );
}

function blankToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

const inputClass = "mt-1 w-full rounded-lg border border-line bg-white px-3 py-2 text-ink outline-none focus:border-moss";
