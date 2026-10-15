<?php

namespace Espo\Custom\Hooks\CPayout;

use Espo\Core\Hook\Hook\AfterRemove;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Keeps Lead.referralPaid and BGC Check.referralPaid in step with the Referrer
 * Payouts linked to them, so Finance records a payment in one place only.
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
            $this->sync('Lead', 'leadId', $leadId);
        }

        $checkIds = array_unique(array_filter([
            $entity->get('bgcCheckId'),
            $entity->getFetched('bgcCheckId'),
        ]));

        foreach ($checkIds as $checkId) {
            $this->sync('CBgcCheck', 'bgcCheckId', $checkId);
        }
    }

    public function afterRemove(Entity $entity, RemoveOptions $options): void
    {
        if ($entity->get('leadId')) {
            $this->sync('Lead', 'leadId', $entity->get('leadId'));
        }

        if ($entity->get('bgcCheckId')) {
            $this->sync('CBgcCheck', 'bgcCheckId', $entity->get('bgcCheckId'));
        }
    }

    private function sync(string $entityType, string $linkAttribute, string $id): void
    {
        $record = $this->entityManager->getEntityById($entityType, $id);

        if (!$record) {
            return;
        }

        $paid = $this->entityManager
            ->getRDBRepository('CPayout')
            ->where([
                $linkAttribute => $id,
                'payeeType' => 'Referrer',
                'status' => 'Paid',
            ])
            ->count() > 0;

        if ((bool) $record->get('referralPaid') === $paid) {
            return;
        }

        $record->set('referralPaid', $paid);
        $this->entityManager->saveEntity($record);
    }
}
