import test from 'node:test'
import assert from 'node:assert/strict'

import { clearPendingConfirmation, mergeBuyerMessages } from './mergeBuyerMessages.js'

test('polling preserves pending confirmation and plan for the same assistant message', () => {
  const previous = [
    { role: 'assistant', content: '欢迎', isWelcome: true },
    {
      id: 42,
      role: 'assistant',
      content: '退款建议待审核',
      need_human: true,
      pending_confirmation: { id: 'confirm-42' },
      plan_steps: [{ id: 'refund', title: '退款试算', status: 'done' }],
      intent_label: '退款申请',
    },
  ]
  const remote = [
    { id: 42, role: 'assistant', content: '退款建议待审核', sources: [], need_human: false },
  ]

  const merged = mergeBuyerMessages(previous, remote)

  assert.equal(merged[0].isWelcome, true)
  assert.equal(merged[1].pending_confirmation.id, 'confirm-42')
  assert.equal(merged[1].plan_steps[0].title, '退款试算')
  assert.equal(merged[1].intent_label, '退款申请')
  assert.equal(merged[1].need_human, true)
})

test('confirmed action clears only the matching pending confirmation', () => {
  const messages = [
    { id: 41, pending_confirmation: { id: 'confirm-41' } },
    { id: 42, pending_confirmation: { id: 'confirm-42' } },
  ]

  const cleared = clearPendingConfirmation(messages, 'confirm-42')

  assert.equal(cleared[0].pending_confirmation.id, 'confirm-41')
  assert.equal(cleared[1].pending_confirmation, null)
})
