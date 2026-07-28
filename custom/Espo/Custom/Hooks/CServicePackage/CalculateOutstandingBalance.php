<?php

namespace Espo\Custom\Hooks\CServicePackage;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

class CalculateOutstandingBalance implements BeforeSave
{
    public static int $order = 5;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $packagePrice = max(0.0, (float) ($entity->get('packagePrice') ?? 0));
        $amountPaid = max(0.0, (float) ($entity->get('amountPaid') ?? 0));

        $entity->set('outstandingBalance', max(0.0, $packagePrice - $amountPaid));

        if ($packagePrice > 0 && $amountPaid >= $packagePrice) {
            $entity->set('paymentStatus', 'Paid');

            return;
        }

        if ($amountPaid > 0) {
            $entity->set('paymentStatus', 'Partially Paid');
        } elseif ($entity->get('paymentStatus') !== 'Overdue') {
            $entity->set('paymentStatus', 'Pending');
        }
    }
}
