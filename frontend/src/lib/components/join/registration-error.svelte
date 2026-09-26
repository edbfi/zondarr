<script lang="ts">
/**
 * Registration error component.
 *
 * Displays error messages for failed registration attempts with:
 * - USERNAME_TAKEN: Prompts user to choose a different username
 * - SERVER_ERROR: Shows failed server name and error message
 * - Other errors: Generic error display
 *
 * @module $lib/components/join/registration-error
 */

import { AlertTriangle, RefreshCw, Server, User } from '@lucide/svelte';
import type { RedemptionErrorResponse } from '$lib/api/client';
import { Button } from '$lib/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card';

interface Props {
	error: RedemptionErrorResponse;
	onRetry?: () => void;
}

const { error, onRetry }: Props = $props();

/**
 * Get user-friendly error title based on error code.
 */
function getErrorTitle(errorCode: string): string {
	switch (errorCode) {
		case 'USERNAME_TAKEN':
			return 'Username Already Taken';
		case 'SERVER_ERROR':
			return 'Server Connection Failed';
		case 'INVALID_INVITATION':
			return 'Invalid Invitation';
		case 'VALIDATION_ERROR':
			return 'Validation Error';
		default:
			return 'Registration Failed';
	}
}

/**
 * Get user-friendly error description based on error code.
 */
function getErrorDescription(
	errorCode: string,
	message: string,
	failedServer?: string | null
): string {
	switch (errorCode) {
		case 'USERNAME_TAKEN':
			return 'This username is already in use. Please choose a different username and try again.';
		case 'SERVER_ERROR':
			return failedServer ? `Failed to create account on ${failedServer}. ${message}` : message;
		default:
			return message;
	}
}

/**
 * Get icon component based on error code.
 */
function getErrorIcon(errorCode: string) {
	switch (errorCode) {
		case 'USERNAME_TAKEN':
			return User;
		case 'SERVER_ERROR':
			return Server;
		default:
			return AlertTriangle;
	}
}

const ErrorIcon = $derived(getErrorIcon(error.error_code));
</script>

<div class="space-y-6" data-registration-error data-error-code={error.error_code}>
	<!-- Error Card -->
	<Card class="border-rose-500/30 bg-rose-500/5">
		<CardHeader>
			<div class="flex items-center gap-3">
				<div class="rounded-full bg-rose-500/15 p-2 text-rose-400">
					<ErrorIcon class="size-5" />
				</div>
				<div>
					<CardTitle class="text-cr-text">{getErrorTitle(error.error_code)}</CardTitle>
					<CardDescription class="text-cr-text-muted">
						{getErrorDescription(error.error_code, error.message, error.failed_server)}
					</CardDescription>
				</div>
			</div>
		</CardHeader>
		{#if error.failed_server}
			<CardContent>
				<div class="flex items-center gap-2 rounded-lg border border-rose-500/20 bg-rose-500/5 p-3">
					<Server class="size-4 text-rose-400" />
					<span class="text-sm text-cr-text-muted">
						Failed server:
						<span class="font-medium text-cr-text" data-failed-server>{error.failed_server}</span>
					</span>
				</div>
			</CardContent>
		{/if}
	</Card>

	<!-- Partial Users (if any were created before failure) -->
	{#if error.partial_users && error.partial_users.length > 0}
		<Card class="border-amber-500/30 bg-amber-500/5">
			<CardHeader>
				<CardTitle class="text-cr-text text-sm">Partial Success</CardTitle>
				<CardDescription class="text-cr-text-muted">
					Some accounts were created before the error occurred.
				</CardDescription>
			</CardHeader>
			<CardContent class="space-y-2">
				{#each error.partial_users as user (user.id)}
					<div class="flex items-center gap-2 rounded-lg border border-cr-border bg-cr-bg p-2">
						<User class="size-4 text-cr-accent" />
						<span class="text-sm text-cr-text">{user.username}</span>
					</div>
				{/each}
			</CardContent>
		</Card>
	{/if}

	<!-- Retry Button -->
	{#if onRetry}
		<Button onclick={onRetry} class="w-full bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
			<RefreshCw class="size-4 mr-2" />
			Try Again
		</Button>
	{/if}
</div>
