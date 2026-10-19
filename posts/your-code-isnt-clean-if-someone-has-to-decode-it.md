---
title: "Your Code Isn't Clean If Someone Has to Decode It"
published: false
description: "Clean code isn't about clever syntax. Learn how intention-revealing names, readable TypeScript, and better code reviews reduce cognitive load and maintenance costs."
tags:
  - cleancode
  - javascript
  - programming
  - productivity
---

> Code is written once, but read hundreds of times. If a developer has to decode what a variable means, the code is already making their job harder.

Imagine reviewing a pull request before a production release. Tests pass, the feature works, and the implementation is short. Then you find:

```js
const d = users.filter(u => u.a && !u.b);
const r = d.map(u => ({ i: u.id, n: u.name }));
return r;
```

You can decode it, but first you need to discover what `a`, `b`, `d`, and `r` mean. Compare that with:

```js
const eligibleUsers = users.filter(
  user => user.isActive && !user.isBlocked
);

return eligibleUsers.map(user => ({
  id: user.id,
  name: user.name,
}));
```

Both versions implement the same intended behavior **if those field meanings are correct**. Only one exposes the business rule without requiring a scavenger hunt.

**Naming is not cosmetic. It is how we make decisions understandable and reviewable.**

## Readability is an engineering constraint

Production code is read by reviewers, new teammates, on-call engineers, and people investigating defects months after the original author has moved on. Every unexplained abbreviation adds a translation task.

In systems that span a Next.js frontend, Node.js APIs, integrations, workflow automation, and databases, that translation cost compounds across boundaries.

As a tech lead working on full-stack platforms and enterprise integrations, I see naming problems hurt most during handoffs and incident investigation, not during the first implementation.

Readable code does not guarantee correct code. It makes assumptions easier to inspect.

## 1. Name the business concept, not the container

Consider a login policy:

```ts
const data = 5;
const count = attempts.length;
const result = count >= data;
```

What is five? What is the result?

```ts
const MAX_FAILED_LOGIN_ATTEMPTS = 5;
const failedLoginAttempts = attempts.length;
const shouldLockAccount =
  failedLoginAttempts >= MAX_FAILED_LOGIN_ATTEMPTS;
```

Now a reviewer can ask the *right* question: should the account lock after five failed attempts, and over what time window?

| Vague | Intention-revealing |
| --- | --- |
| `data` | `activeSubscriptions` |
| `list` | `pendingInvoices` |
| `flag` | `requiresManualReview` |
| `num` | `unreadMessageCount` |
| `temp` | `normalizedEmail` |

These replacements only help if they truthfully describe the values. A confidently wrong name can be worse than a short one.

## 2. Make conditions read like decisions

```ts
if (user.a && order.t > 1000 && !order.f) {
  queue.push(order);
}
```

Assuming these fields represent verification, amount, and fraud hold:

```ts
const isVerifiedCustomer = user.isVerified;
const exceedsReviewThreshold = order.totalAmount > 1_000;
const hasNoFraudHold = !order.hasFraudHold;

const requiresManualReview =
  isVerifiedCustomer &&
  exceedsReviewThreshold &&
  hasNoFraudHold;

if (requiresManualReview) {
  reviewQueue.push(order);
}
```

Now the rule can be discussed in domain language. However, avoid extracting every tiny expression into a constant. Name intermediate results when they reveal a meaningful concept or make a complex decision testable.

## 3. Let TypeScript types communicate intent

```ts
type Item = {
  id: string;
  s: string;
  n: number;
};

function process(items: Item[]): Item[] {
  return items.filter(item => item.s === 'paid');
}
```

The compiler knows the shape, but the next engineer still has to decode it.

```ts
type InvoiceStatus = 'draft' | 'issued' | 'paid';

type Invoice = {
  id: string;
  status: InvoiceStatus;
  amountInMinorUnits: number;
};

function getPaidInvoices(invoices: Invoice[]): Invoice[] {
  return invoices.filter(invoice => invoice.status === 'paid');
}
```

`amountInMinorUnits` prevents ambiguity about currency representation. Good naming extends beyond local variables to API contracts, database columns, events, and workflow steps.

## 4. Comments should explain *why*, not decode *what*

Weak:

```js
// Check if user can access dashboard
if (u.r === 2 && u.a) {
  showDashboard();
}
```

Better:

```js
if (user.hasDashboardAccess && user.isActive) {
  showDashboard();
}
```

But keep comments that preserve non-obvious operational constraints:

```ts
// The payment provider may retry callbacks out of order.
// Ignore events older than the last successfully applied update.
if (event.createdAt <= payment.lastAppliedEventAt) {
  return;
}
```

That comment contains knowledge a future refactor could otherwise erase.

## 5. Don't make names into sentences

```ts
const listOfAllUsersWhoAreCurrentlyActiveAndNotBlocked = [];
```

Length alone is not clarity. In a function where eligibility is defined, `eligibleUsers` may be sufficient; elsewhere `activeUnblockedUsers` could be more accurate.

Useful conventions:

- Use domain vocabulary instead of `data`, `thing`, or `value`.
- Name booleans as predicates: `isActive`, `hasAccess`, `canRetry`.
- Include units when needed: `timeoutMs`, `distanceKm`, `amountInMinorUnits`.
- Avoid abbreviations except widely understood ones such as URL or HTTP.
- Use short names only in small, familiar scopes.

## 6. Review names as part of correctness

```ts
const validOrders = orders.filter(order => order.total > 0);
```

Does a positive total really mean an order is *valid* for fulfillment? Payment? Reporting? The name overpromises.

```ts
const ordersWithPositiveTotals = orders.filter(
  order => order.total > 0
);
```

If eligibility is the actual business concept, model it explicitly:

```ts
function isEligibleForFulfillment(order: Order): boolean {
  return (
    order.paymentStatus === 'paid' &&
    order.fulfillmentStatus === 'pending' &&
    !order.isOnHold
  );
}
```

The function gives the business rule a stable place to live, review, and test.

### My pull-request naming checklist

1. Can a reviewer understand the key decision without opening unrelated files?
2. Do names describe what values and functions *actually guarantee*?
3. Do boolean names read like yes/no questions?
4. Are units and amounts explicit where ambiguity matters?
5. Do comments preserve context rather than translate abbreviations?
6. Does the code use the team's shared domain terminology?

## Clean code is a team-level optimization

Clever code can be satisfying to write. Production engineering is collaboration across time: today's author, tomorrow's reviewer, and next quarter's on-call engineer must all understand the same decisions.

Complex systems always require thought. The goal is to eliminate **unnecessary decoding** so engineers can focus on the real problem.

**Write code that reveals its intent. Future maintainers should spend their energy understanding the problem—not translating variable names.**

What's a variable or function name you've encountered that made debugging unnecessarily difficult? Share how your team improved it.

---

## About the Author

I write about software architecture, AI, automation, and real-world engineering challenges.

Explore more of my work and technical insights at [sanukhan.dev](https://sanukhan.dev/).
