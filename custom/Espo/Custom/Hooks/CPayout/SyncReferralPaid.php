<?php

namespace Espo\Custom\Hooks\CPayout;

use Espo\Core\Hook\Hook\AfterRemove;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Keeps Lead.referralPaid in step with the Referrer Payouts linked to the lead,
 * so Finance records a payment in one place only.
 */
class SyncReferralPaid implements AfterSave, AfterRemove
{
    public static int $order = 20;

    public function __construct(
        private EntityManager $entityManager
    ) {}

    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        $leadIds = array_unique(array_filter([
            $entity->get('leadId'),
            $entity->getFetched('leadId'),
        ]));

        foreach ($leadIds as $leadId) {
            $this->sync($leadId);
        }
    }

    public function afterRemove(Entity $entity, RemoveOptions $options): void
    {
        if ($entity->get('leadId')) {
            $this->sync($entity->get('leadId'));
        }
    }

    private function sync(string $leadId): void
    {
        $lead = $this->entityManager->getEntityById('Lead', $leadId);

        if (!$lead) {
            return;
        }

        $paid = $this->entityManager
            ->getRDBRepository('CPayout')
            ->where([
                'leadId' => $leadId,
                'payeeType' => 'Referrer',
                'status' => 'Paid',
            ])
            ->count() > 0;

        if ((bool) $lead->get('referralPaid') === $paid) {
            return;
        }

        $lead->set('referralPaid', $paid);
        $this->entityManager->saveEntity($lead);
    }
}
