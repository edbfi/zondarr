<script lang="ts">
/**
 * User permissions editor component.
 *
 * Provides toggle switches for user permissions on the media server:
 * - can_stream: Whether the user can stream/play content
 * - can_download: Whether the user can download content
 * - can_sync: Whether the user can sync content for offline use
 * - can_transcode: Whether the user can use transcoding
 *
 * Each toggle saves immediately on change with optimistic UI and rollback on error.
 *
 * @module $lib/components/users/user-permissions-editor
 */

import { toast } from 'svelte-sonner';
import { type UpdateUserPermissions, updateUserPermissions } from '$lib/api/client';
import { ApiError, asErrorResponse, getErrorMessage } from '$lib/api/errors';
import { Label } from '$lib/components/ui/label';

interface Props {
	userId: string;
	disabled?: boolean;
	supportedPermissions?: string[];
}

const { userId, disabled = false, supportedPermissions }: Props = $props();

function isPermissionSupported(key: string): boolean {
	if (!supportedPermissions) return true;
	return supportedPermissions.includes(key);
}

// Permission states - start as undefined (unknown from server)
let canStream = $state<boolean | undefined>(undefined);
let canDownload = $state<boolean | undefined>(undefined);
let canSync = $state<boolean | undefined>(undefined);
let canTranscode = $state<boolean | undefined>(undefined);

// Loading states for each permission
let loadingStream = $state(false);
let loadingDownload = $state(false);
let loadingSync = $state(false);
let loadingTranscode = $state(false);

/**
 * Handle permission toggle with optimistic update and rollback.
 */
async function handlePermissionChange(
	key: keyof UpdateUserPermissions,
	newValue: boolean,
	setLoading: (v: boolean) => void,
	setValue: (v: boolean | undefined) => void,
	currentValue: boolean | undefined
) {
	if (disabled) return;

	setLoading(true);
	// Optimistic update
	setValue(newValue);

	try {
		const result = await updateUserPermissions(userId, { [key]: newValue });

		if (result.error) {
			const status = result.response?.status ?? 500;
			const errorBody = asErrorResponse(result.error);
			throw new ApiError(
				status,
				errorBody?.error_code ?? 'UNKNOWN_ERROR',
				errorBody?.detail ?? 'Failed to update permission'
			);
		}

		toast.success(`Permission updated`, {
			description: `${formatPermissionName(key)} is now ${newValue ? 'enabled' : 'disabled'}`
		});
	} catch (error) {
		// Rollback on error
		setValue(currentValue);
		toast.error('Failed to update permission', {
			description: getErrorMessage(error)
		});
	} finally {
		setLoading(false);
	}
}

/**
 * Format permission key to human-readable name.
 */
function formatPermissionName(key: string): string {
	switch (key) {
		case 'can_stream':
			return 'Streaming';
		case 'can_download':
			return 'Downloads';
		case 'can_sync':
			return 'Sync';
		case 'can_transcode':
			return 'Transcoding';
		default:
			return key;
	}
}

// Handlers for each permission
function toggleStream() {
	const newValue = !(canStream ?? true);
	handlePermissionChange(
		'can_stream',
		newValue,
		(v) => {
			loadingStream = v;
		},
		(v) => {
			canStream = v;
		},
		canStream
	);
}

function toggleDownload() {
	const newValue = !(canDownload ?? true);
	handlePermissionChange(
		'can_download',
		newValue,
		(v) => {
			loadingDownload = v;
		},
		(v) => {
			canDownload = v;
		},
		canDownload
	);
}

function toggleSync() {
	const newValue = !(canSync ?? true);
	handlePermissionChange(
		'can_sync',
		newValue,
		(v) => {
			loadingSync = v;
		},
		(v) => {
			canSync = v;
		},
		canSync
	);
}

function toggleTranscode() {
	const newValue = !(canTranscode ?? true);
	handlePermissionChange(
		'can_transcode',
		newValue,
		(v) => {
			loadingTranscode = v;
		},
		(v) => {
			canTranscode = v;
		},
		canTranscode
	);
}

/**
 * Check if any permission is loading.
 */
const anyLoading = $derived(
	(isPermissionSupported('can_stream') && loadingStream) ||
		(isPermissionSupported('can_download') && loadingDownload) ||
		(isPermissionSupported('can_sync') && loadingSync) ||
		(isPermissionSupported('can_transcode') && loadingTranscode)
);
</script>

<div class="space-y-4">
	<p class="text-cr-text-muted text-xs">
		Toggle permissions to control what this user can do on the media server. Changes are saved
		immediately.
	</p>

	<div class="grid gap-4 sm:grid-cols-2">
		<!-- Streaming Permission -->
		{#if isPermissionSupported('can_stream')}
			<div
				class="flex items-center justify-between gap-3 rounded-lg border border-cr-border bg-cr-bg p-3"
			>
				<div class="space-y-0.5">
					<Label class="text-cr-text text-sm font-medium">Streaming</Label>
					<p class="text-cr-text-muted text-xs">Can stream and play content</p>
				</div>
				<button
					type="button"
					role="switch"
					aria-checked={canStream ?? true}
					aria-label="Toggle streaming permission"
					disabled={disabled || anyLoading}
					onclick={toggleStream}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cr-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {(canStream ?? true) ? 'bg-cr-accent' : 'bg-cr-border'}"
					data-permission="can_stream"
				>
					{#if loadingStream}
						<span class="absolute inset-0 flex items-center justify-center">
							<span
								class="size-3 animate-spin rounded-full border-2 border-white border-t-transparent"
							></span>
						</span>
					{:else}
						<span
							class="pointer-events-none inline-block size-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform {(canStream ?? true) ? 'translate-x-5' : 'translate-x-0'}"
						></span>
					{/if}
				</button>
			</div>
		{/if}

		<!-- Download Permission -->
		{#if isPermissionSupported('can_download')}
			<div
				class="flex items-center justify-between gap-3 rounded-lg border border-cr-border bg-cr-bg p-3"
			>
				<div class="space-y-0.5">
					<Label class="text-cr-text text-sm font-medium">Downloads</Label>
					<p class="text-cr-text-muted text-xs">Can download content locally</p>
				</div>
				<button
					type="button"
					role="switch"
					aria-checked={canDownload ?? true}
					aria-label="Toggle download permission"
					disabled={disabled || anyLoading}
					onclick={toggleDownload}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cr-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {(canDownload ?? true) ? 'bg-cr-accent' : 'bg-cr-border'}"
					data-permission="can_download"
				>
					{#if loadingDownload}
						<span class="absolute inset-0 flex items-center justify-center">
							<span
								class="size-3 animate-spin rounded-full border-2 border-white border-t-transparent"
							></span>
						</span>
					{:else}
						<span
							class="pointer-events-none inline-block size-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform {(canDownload ?? true) ? 'translate-x-5' : 'translate-x-0'}"
						></span>
					{/if}
				</button>
			</div>
		{/if}

		<!-- Sync Permission -->
		{#if isPermissionSupported('can_sync')}
			<div
				class="flex items-center justify-between gap-3 rounded-lg border border-cr-border bg-cr-bg p-3"
			>
				<div class="space-y-0.5">
					<Label class="text-cr-text text-sm font-medium">Sync</Label>
					<p class="text-cr-text-muted text-xs">Can sync content for offline use</p>
				</div>
				<button
					type="button"
					role="switch"
					aria-checked={canSync ?? true}
					aria-label="Toggle sync permission"
					disabled={disabled || anyLoading}
					onclick={toggleSync}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cr-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {(canSync ?? true) ? 'bg-cr-accent' : 'bg-cr-border'}"
					data-permission="can_sync"
				>
					{#if loadingSync}
						<span class="absolute inset-0 flex items-center justify-center">
							<span
								class="size-3 animate-spin rounded-full border-2 border-white border-t-transparent"
							></span>
						</span>
					{:else}
						<span
							class="pointer-events-none inline-block size-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform {(canSync ?? true) ? 'translate-x-5' : 'translate-x-0'}"
						></span>
					{/if}
				</button>
			</div>
		{/if}

		<!-- Transcode Permission -->
		{#if isPermissionSupported('can_transcode')}
			<div
				class="flex items-center justify-between gap-3 rounded-lg border border-cr-border bg-cr-bg p-3"
			>
				<div class="space-y-0.5">
					<Label class="text-cr-text text-sm font-medium">Transcoding</Label>
					<p class="text-cr-text-muted text-xs">Can request content transcoding</p>
				</div>
				<button
					type="button"
					role="switch"
					aria-checked={canTranscode ?? true}
					aria-label="Toggle transcoding permission"
					disabled={disabled || anyLoading}
					onclick={toggleTranscode}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cr-accent focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 {(canTranscode ?? true) ? 'bg-cr-accent' : 'bg-cr-border'}"
					data-permission="can_transcode"
				>
					{#if loadingTranscode}
						<span class="absolute inset-0 flex items-center justify-center">
							<span
								class="size-3 animate-spin rounded-full border-2 border-white border-t-transparent"
							></span>
						</span>
					{:else}
						<span
							class="pointer-events-none inline-block size-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform {(canTranscode ?? true) ? 'translate-x-5' : 'translate-x-0'}"
						></span>
					{/if}
				</button>
			</div>
		{/if}
	</div>
</div>
