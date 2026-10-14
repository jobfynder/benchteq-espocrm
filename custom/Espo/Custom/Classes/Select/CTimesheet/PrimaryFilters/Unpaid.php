<?php

namespace Espo\Custom\Classes\Select\CTimesheet\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class Unpaid implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['status' => ['Held', 'No-Show'], 'payoutId' => null]);
    }
}
