<?php

namespace Espo\Custom\Hooks\CInterviewSession;

use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * A session can be set to Held or No-Show only after the customer has paid.
 */
class RequirePaymentBeforeHeld implements BeforeSave
{
    public static int $order = 5;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if (!in_array($entity->get('status'), ['Held', 'No-Show'], true)) {
            return;
        }

        if ($entity->get('paymentStatus') === 'Paid') {
            return;
        }

        if (
            !$entity->isNew() &&
            !$entity->isAttributeChanged('status') &&
            !$entity->isAttributeChanged('paymentStatus')
        ) {
            return;
        }

        throw new BadRequest('Mark the session as Paid before setting it to Held or No-Show.');
    }
}
