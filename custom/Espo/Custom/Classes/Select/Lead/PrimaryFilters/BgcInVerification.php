<?php

namespace Espo\Custom\Classes\Select\Lead\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class BgcInVerification implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['serviceType' => 'BGC', 'bgcStatus' => 'In Verification']);
    }
}
