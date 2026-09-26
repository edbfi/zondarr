<script lang="ts">
/**
 * Create invitation dialog component.
 *
 * Provides a modal dialog for creating new invitations with:
 * - Form validation via Zod
 * - API submission with error handling
 * - Success/error toast notifications
 * - Auto-close on successful creation
 *
 * @module $lib/components/invitations/create-invitation-dialog
 */

import { Plus } from '@lucide/svelte';
import {
	createInvitation,
	getWizards,
	type MediaServerWithLibrariesResponse,
	type WizardResponse,
	withErrorHandling
} from '$lib/api/client';
import { asErrorResponse, asValidationErrorResponse } from '$lib/api/errors';
import { Button } from '$lib/components/ui/button';
import * as Dialog from '$lib/components/ui/dialog';
import {
	type CreateInvitationInput,
	createInvitationSchema,
	transformCreateFormData
} from '$lib/schemas/invitation';
import { showError, showSuccess } from '$lib/utils/toast';
import InvitationFormSimple from './invitation-form-simple.svelte';

interface Props {
	servers: MediaServerWithLibrariesResponse[];
	onSuccess?: () => void;
}

const { servers, onSuccess }: Props = $props();

// Dialog open state
let open = $state(false);

// Fetch wizards when dialog opens, reset form when it closes
$effect(() => {
	if (open) {
		fetchWizards();
	} else {
		resetForm();
	}
});

// Submitting state
let submitting = $state(false);

// Available wizards
let wizards = $state<WizardResponse[]>([]);
let loadingWizards = $state(false);

// Form data state
let formData = $state<CreateInvitationInput>({
	server_ids: [],
	code: '',
	expires_at: '',
	max_uses: undefined,
	duration_days: undefined,
	library_ids: [],
	pre_wizard_id: '',
	post_wizard_id: ''
});

// Validation errors
let errors = $state<Record<string, string[]>>({});

/**
 * Fetch available wizards when dialog opens.
 */
async function fetchWizards() {
	loadingWizards = true;
	try {
		const result = await getWizards({ page_size: 100 });
		if (result.data) {
			// Only show enabled wizards
			wizards = result.data.items.filter((w) => w.enabled);
		}
	} catch (error) {
		showError(
			'Failed to load wizards',
			error instanceof Error ? error.message : 'An unexpected error occurred'
		);
	} finally {
		loadingWizards = false;
	}
}

/**
 * Reset form to initial state.
 */
function resetForm() {
	formData = {
		server_ids: [],
		code: '',
		expires_at: '',
		max_uses: undefined,
		duration_days: undefined,
		library_ids: [],
		pre_wizard_id: '',
		post_wizard_id: ''
	};
	errors = {};
}

/**
 * Validate form data.
 */
function validateForm(): boolean {
	const result = createInvitationSchema.safeParse(formData);
	if (!result.success) {
		const fieldErrors: Record<string, string[]> = {};
		for (const issue of result.error.issues) {
			const path = issue.path.join('.');
			if (!fieldErrors[path]) {
				fieldErrors[path] = [];
			}
			fieldErrors[path].push(issue.message);
		}
		errors = fieldErrors;
		return false;
	}
	errors = {};
	return true;
}

/**
 * Handle form submission.
 */
async function handleSubmit() {
	if (!validateForm()) {
		showError('Please fix the errors below');
		return;
	}

	submitting = true;
	try {
		const data = transformCreateFormData(formData);
		const result = await withErrorHandling(() => createInvitation(data), {
			showErrorToast: false
		});

		if (result.error) {
			const validationBody = asValidationErrorResponse(result.error);
			if (validationBody?.field_errors) {
				const fieldErrors: Record<string, string[]> = {};
				for (const fe of validationBody.field_errors) {
					fieldErrors[fe.field] = fe.messages;
				}
				errors = fieldErrors;
			}

			const errorBody = asErrorResponse(result.error);
			showError('Failed to create invitation', errorBody?.detail ?? 'An error occurred');
			return;
		}

		// Success
		showSuccess('Invitation created successfully', `Code: ${result.data?.code}`);

		// Close dialog (form resets via $effect watching open)
		open = false;

		// Notify parent to refresh list
		onSuccess?.();
	} finally {
		submitting = false;
	}
}

/**
 * Handle cancel button.
 */
function handleCancel() {
	open = false;
}
</script>

<Dialog.Root bind:open>
	<Dialog.Trigger>
		{#snippet child({
	props
})}
			<Button {...props} class="bg-cr-accent text-cr-bg hover:bg-cr-accent-hover">
				<Plus class="size-4" />
				Create Invitation
			</Button>
		{/snippet}
	</Dialog.Trigger>

	<Dialog.Content class="border-cr-border bg-cr-surface sm:max-w-xl max-h-[90vh] overflow-y-auto">
		<Dialog.Header>
			<Dialog.Title class="text-cr-text flex items-center gap-2">
				<Plus class="size-5 text-cr-accent" />
				Create Invitation
			</Dialog.Title>
			<Dialog.Description class="text-cr-text-muted">
				Create a new invitation code for user onboarding. Select target servers and configure
				optional restrictions.
			</Dialog.Description>
		</Dialog.Header>

		<div class="mt-4">
			<InvitationFormSimple
				bind:formData
				{errors}
				{servers}
				{wizards}
				{loadingWizards}
				mode="create"
				{submitting}
				onSubmit={handleSubmit}
				onCancel={handleCancel}
			/>
		</div>
	</Dialog.Content>
</Dialog.Root>
