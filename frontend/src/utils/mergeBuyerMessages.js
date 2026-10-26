export function mergeBuyerMessages(previous, remote) {
  const welcomeMessage = previous.find((message) => message.isWelcome)
  const previousById = new Map(
    previous.filter((message) => message.id).map((message) => [message.id, message]),
  )

  const merged = remote.map((message) => {
    const local = previousById.get(message.id)
    return {
      ...message,
      need_human: local?.need_human ?? message.need_human ?? false,
      pending_confirmation: local?.pending_confirmation ?? message.pending_confirmation ?? null,
      plan_steps: local?.plan_steps ?? message.plan_steps ?? [],
      intent_label: local?.intent_label ?? message.intent_label ?? null,
    }
  })

  return welcomeMessage ? [welcomeMessage, ...merged] : merged
}

export function clearPendingConfirmation(messages, confirmationId) {
  return messages.map((message) => (
    message.pending_confirmation?.id === confirmationId
      ? { ...message, pending_confirmation: null }
      : message
  ))
}
