import { Link, useNavigate } from "react-router";
import { createAutomation, type AutomationInput } from "../api";
import { AutomationForm } from "../components/AutomationForm";

export function RegisterAutomation() {
  const navigate = useNavigate();

  async function handleSubmit(input: AutomationInput) {
    const created = await createAutomation(input);
    navigate(`/automations/${created.id}`);
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link className="text-sm text-moss" to="/">
        Back to automations
      </Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">Add automation</h1>
      <p className="mt-2 text-ink/70">
        Point Tâchibou at a script you already have. Nothing is copied or changed.
      </p>
      <div className="mt-8">
        <AutomationForm submitLabel="Save automation" onSubmit={handleSubmit} />
      </div>
    </div>
  );
}
