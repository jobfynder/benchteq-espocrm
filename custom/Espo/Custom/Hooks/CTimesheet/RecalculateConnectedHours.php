<?php

namespace Espo\Custom\Hooks\CTimesheet;

use Espo\Core\Hook\Hook\AfterRemove;
use Espo\Core\Hook\Hook\AfterSave;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\ORM\Repository\Option\RemoveOptions;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Connected Hrs on a Payment Block = hours of its Held and No-Show timesheets.
 * Planned and Cancelled timesheets do not count.
 */
class RecalculateConnectedHours implements AfterSave, AfterRemove
{
    public static int $order = 20;

    private const COUNTED_STATUSES = ['Held', 'No-Show'];

    public function __construct(
        private EntityManager $entityManager
    ) {}

    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        $blockIds = array_unique(array_filter([
            $entity->get('paymentBlockId'),
            $entity->getFetched('paymentBlockId'),
        ]));

        foreach ($blockIds as $blockId) {
            $this->recalculate($blockId);
        }
    }

    public function afterRemove(Entity $entity, RemoveOptions $options): void
    {
        $blockId = $entity->get('paymentBlockId');

        if ($blockId) {
            $this->recalculate($blockId);
        }
    }

    private function recalculate(string $blockId): void
    {
        $block = $this->entityManager->getEntityById('CPaymentBlock', $blockId);

        if (!$block) {
            return;
        }

        $sum = $this->entityManager
            ->getRDBRepository('CTimesheet')
            ->where([
                'paymentBlockId' => $blockId,
                'status' => self::COUNTED_STATUSES,
            ])
            ->sum('hours');

        $sum = round((float) $sum, 2);

        if ($block->get('connectedHrs') !== null && abs((float) $block->get('connectedHrs') - $sum) < 0.001) {
            return;
        }

        $block->set('connectedHrs', $sum);
        $this->entityManager->saveEntity($block);
    }
}
