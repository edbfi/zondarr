<script lang="ts">
/**
 * Registration form component.
 *
 * Provides a form for creating a user account with:
 * - Username validation (3-32 chars, lowercase, starts with letter)
 * - Password validation (minimum 8 characters)
 * - Optional email field
 * - Inline validation errors
 *
 * Uses direct state binding for SPA usage.
 *
 * @module $lib/components/join/registration-form
 */

import { Eye, EyeOff, Lock, Mail, User } from '@lucide/svelte';
import { Button } from '$lib/components/ui/button';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import type { RegistrationInput } from '$lib/schemas/join';

interface Props {
	formData: RegistrationInput;
	errors: Record<string, string[]>;
	submitting?: boolean;
	onSubmit: () => void;
}

let { formData = $bindable(), errors, submitting = false, onSubmit }: Props = $props();

// Password visibility toggle
let showPassword = $state(false);

/**
 * Handle form submission.
 */
function handleSubmit(e: Event) {
	e.preventDefault();
	onSubmit();
}

/**
 * Get error messages for a field.
 */
function getFieldErrors(field: string): string[] {
	return errors[field] ?? [];
}

/**
 * Toggle password visibility.
 */
function togglePasswordVisibility() {
	showPassword = !showPassword;
}
</script>

<form onsubmit={handleSubmit} class="space-y-6" data-registration-form>
	<!-- Username (Required) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<User class="size-4 text-cr-accent" />
			Username
			<span class="text-rose-400">*</span>
		</Label>
		<Input
			type="text"
			value={formData.username}
			oninput={(e) => (formData.username = e.currentTarget.value)}
			placeholder="e.g., johndoe"
			class="border-cr-border bg-cr-surface text-cr-text placeholder:text-cr-text-muted"
			autocomplete="username"
			autocapitalize="none"
			spellcheck="false"
			data-field-username
		/>
		<p class="text-cr-text-muted text-xs">
			3-32 characters, lowercase letters, numbers, and underscores. Must start with a letter.
		</p>
		{#if getFieldErrors('username').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="username">
				{#each getFieldErrors('username') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Password (Required) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<Lock class="size-4 text-cr-accent" />
			Password
			<span class="text-rose-400">*</span>
		</Label>
		<div class="relative">
			<Input
				type={showPassword ? 'text' : 'password'}
				value={formData.password}
				oninput={(e) => (formData.password = e.currentTarget.value)}
				placeholder="Enter a secure password"
				class="border-cr-border bg-cr-surface text-cr-text placeholder:text-cr-text-muted pr-10"
				autocomplete="new-password"
				data-field-password
			/>
			<button
				type="button"
				onclick={togglePasswordVisibility}
				class="absolute right-3 top-1/2 -translate-y-1/2 text-cr-text-muted hover:text-cr-text transition-colors"
				aria-label={showPassword ? 'Hide password' : 'Show password'}
			>
				{#if showPassword}
					<EyeOff class="size-4" />
				{:else}
					<Eye class="size-4" />
				{/if}
			</button>
		</div>
		<p class="text-cr-text-muted text-xs">Minimum 8 characters</p>
		{#if getFieldErrors('password').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="password">
				{#each getFieldErrors('password') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Email (Optional) -->
	<div class="space-y-2">
		<Label class="text-cr-text flex items-center gap-2">
			<Mail class="size-4 text-cr-accent" />
			Email
			<span class="text-cr-text-muted text-xs">(optional)</span>
		</Label>
		<Input
			type="email"
			value={formData.email}
			oninput={(e) => (formData.email = e.currentTarget.value)}
			placeholder="you@example.com"
			class="border-cr-border bg-cr-surface text-cr-text placeholder:text-cr-text-muted"
			autocomplete="email"
			data-field-email
		/>
		<p class="text-cr-text-muted text-xs">Used for password recovery and notifications</p>
		{#if getFieldErrors('email').length > 0}
			<div class="text-rose-400 text-sm" data-field-error="email">
				{#each getFieldErrors('email') as error}
					<p>{error}</p>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Submit Button -->
	<Button
		type="submit"
		disabled={submitting}
		class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover"
	>
		{#if submitting}
			<span
				class="size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2"
			></span>
			Creating Account...
		{:else}
			Create Account
		{/if}
	</Button>
</form>
