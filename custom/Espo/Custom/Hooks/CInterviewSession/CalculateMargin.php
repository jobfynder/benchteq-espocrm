<?php

namespace Espo\Custom\Hooks\CInterviewSession;

use Espo\Core\Hook\Hook\BeforeSave;
use Espo\Custom\Classes\Margin;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * Keeps the margin (income minus cost, in INR) up to date.
 */
class CalculateMargin implements BeforeSave
{
    public static int $order = 30;

    public function __construct(
        private Margin $margin
    ) {}

    public function beforeSave(Entity $entity, SaveOptions $options): void
    {
        $this->margin->apply($entity, 'customerFee', 'supporterFee');
    }
}
