<?php

namespace Espo\Custom\Hooks\CProvider;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

class EnforceInrFees implements BeforeSave
{
    public static int $order = 5;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        foreach (['standardFlatFee', 'bgcFeeUS', 'bgcFeeIndia'] as $field) {
            if ($entity->get($field) !== null) {
                $entity->set($field . 'Currency', 'INR');
            }
        }
    }
}
