<?php

namespace Espo\Custom\Hooks\CPayout;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

class EnforceInrAmount implements BeforeSave
{
    public static int $order = 5;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        if ($entity->get('amount') !== null) {
            $entity->set('amountCurrency', 'INR');
        }
    }
}
