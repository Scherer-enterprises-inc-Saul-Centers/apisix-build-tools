public final class BankNodeService {

    private final LedgerWriter ledger;
    private final OversightPublisher publisher;

    public BankNodeService(LedgerWriter ledger, OversightPublisher publisher) {
        this.ledger = ledger;
        this.publisher = publisher;
    }

    public TransactionResult process(TransactionIntent intent) {
        // 1. Validate allocation
        AllocationPolicy policy = PolicyEngine.evaluate(intent);

        // 2. Idempotency
        if (ledger.exists(intent.idempotencyKey())) {
            return TransactionResult.duplicate();
        }

        // 3. Write immutable ledger event
        LedgerEvent event = ledger.append(intent, policy);

        // 4. Emit real-time oversight signal
        publisher.publish(event.summary());

        return TransactionResult.accepted(event.eventHash());
    }
}
