<script lang="ts">
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import { loginSchema } from '$lib/schemas/auth';

interface Props {
	onsubmit: (username: string, password: string) => Promise<void>;
}

const { onsubmit }: Props = $props();

let username = $state('');
let password = $state('');
let errors = $state<Record<string, string>>({});
let loading = $state(false);

async function handleSubmit(e: SubmitEvent) {
	e.preventDefault();
	errors = {};

	const result = loginSchema.safeParse({ username, password });
	if (!result.success) {
		for (const issue of result.error.issues) {
			const field = issue.path[0];
			if (field && typeof field === 'string') {
				errors[field] = issue.message;
			}
		}
		return;
	}

	loading = true;
	try {
		await onsubmit(username, password);
	} finally {
		loading = false;
	}
}
</script>

<form onsubmit={handleSubmit} class="flex flex-col gap-4">
	<div class="flex flex-col gap-1.5">
		<Label for="login-username" class="text-cr-text">Username</Label>
		<Input
			id="login-username"
			type="text"
			bind:value={username}
			placeholder="Enter username"
			autocomplete="username"
			class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-dim"
		/>
		{#if errors.username}
			<p class="text-xs text-red-400">{errors.username}</p>
		{/if}
	</div>

	<div class="flex flex-col gap-1.5">
		<Label for="login-password" class="text-cr-text">Password</Label>
		<Input
			id="login-password"
			type="password"
			bind:value={password}
			placeholder="Enter password"
			autocomplete="current-password"
			class="border-cr-border bg-cr-bg text-cr-text placeholder:text-cr-text-dim"
		/>
		{#if errors.password}
			<p class="text-xs text-red-400">{errors.password}</p>
		{/if}
	</div>

	<Button
		type="submit"
		disabled={loading}
		class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
	>
		{#if loading}
			Signing in...
		{:else}
			Sign in
		{/if}
	</Button>
</form>
