<script lang="ts">
/**
 * Quiz Interaction Config Editor
 *
 * Provides admin UI for configuring quiz interaction settings.
 */
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import * as RadioGroup from '$lib/components/ui/radio-group';
import type { ConfigEditorProps } from '../registry';

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

function updateField(field: string, value: unknown) {
	onConfigChange({ ...rawConfig, [field]: value });
}

function addOption() {
	const options = (rawConfig.options as string[]) ?? [];
	onConfigChange({ ...rawConfig, options: [...options, ''] });
}

function removeOption(index: number) {
	const options = (rawConfig.options as string[]) ?? [];
	const newOptions = options.filter((_, i) => i !== index);
	let correctIndex = (rawConfig.correct_answer_index as number) ?? 0;
	if (correctIndex >= newOptions.length) {
		correctIndex = Math.max(0, newOptions.length - 1);
	}
	onConfigChange({ ...rawConfig, options: newOptions, correct_answer_index: correctIndex });
}

function updateOption(index: number, value: string) {
	const options = [...((rawConfig.options as string[]) ?? [])];
	options[index] = value;
	onConfigChange({ ...rawConfig, options });
}
</script>

<div class="flex flex-col gap-4">
	<div class="flex flex-col gap-2">
		<Label for="question" class="text-cr-text">Question</Label>
		<Input
			id="question"
			value={(rawConfig.question as string) ?? ''}
			oninput={(e) => updateField('question', e.currentTarget.value)}
			placeholder="Enter your question"
			class="border-cr-border bg-cr-bg text-cr-text"
		/>
		{#if errors.question}
			<p class="text-xs text-destructive">{errors.question[0]}</p>
		{/if}
	</div>

	<div class="flex flex-col gap-2">
		<div class="flex items-center justify-between">
			<Label class="text-cr-text">Answer Options</Label>
			<Button
				variant="outline"
				size="sm"
				onclick={addOption}
				disabled={((rawConfig.options as string[] | undefined)?.length ?? 0) >= 10}
				class="border-cr-border text-cr-text-muted"
			>
				Add Option
			</Button>
		</div>

		<RadioGroup.Root
			value={String(rawConfig.correct_answer_index ?? 0)}
			onValueChange={(val) => updateField('correct_answer_index', parseInt(val))}
			class="flex flex-col gap-2"
		>
			{#each (rawConfig.options as string[]) ?? [] as option, index}
				<div class="flex items-center gap-2">
					<div class="flex items-center justify-center w-8 shrink-0">
						<RadioGroup.Item value={String(index)} />
					</div>
					<Input
						value={option}
						oninput={(e) => updateOption(index, e.currentTarget.value)}
						placeholder={`Option ${index + 1}`}
						class="flex-1 border-cr-border bg-cr-bg text-cr-text"
					/>
					<Button
						variant="ghost"
						size="sm"
						onclick={() => removeOption(index)}
						disabled={((rawConfig.options as string[] | undefined)?.length ?? 0) <= 2}
						class="text-cr-text-muted hover:text-destructive"
					>
						×
					</Button>
				</div>
			{/each}
		</RadioGroup.Root>

		<p class="text-xs text-cr-text-muted">Select the radio button next to the correct answer.</p>
		{#if errors.options}
			<p class="text-xs text-destructive">{errors.options[0]}</p>
		{/if}
		{#if errors.correct_answer_index}
			<p class="text-xs text-destructive">{errors.correct_answer_index[0]}</p>
		{/if}
	</div>
</div>
