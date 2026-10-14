<?php

namespace Espo\Custom\Classes\Select\CPayout\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class Due implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['status' => 'Due']);
    }
}
