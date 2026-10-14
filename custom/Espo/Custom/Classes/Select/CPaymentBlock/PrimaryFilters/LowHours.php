<?php

namespace Espo\Custom\Classes\Select\CPaymentBlock\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class LowHours implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['status' => 'Active', 'remainingHrs<=' => 5]);
    }
}
