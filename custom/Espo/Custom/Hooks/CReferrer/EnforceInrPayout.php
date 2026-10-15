<?php

namespace Espo\Custom\Hooks\CReferrer;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * What we pay out is always in INR.
 */
class EnforceInrPayout implements BeforeSave
{
    public static int $order = 5;

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        foreach (['referralFee'] as $field) {
            if ($entity->get($field) !== null) {
                $entity->set($field . 'Currency', 'INR');
            }
        }
    }
}
