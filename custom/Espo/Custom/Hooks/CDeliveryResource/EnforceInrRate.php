<?php

namespace Espo\Custom\Hooks\CDeliveryResource;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

class EnforceInrRate implements BeforeSave
{
    public static int $order = 5;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->get('rate') !== null) {
            $entity->set('rateCurrency', 'INR');
        }
    }
}
