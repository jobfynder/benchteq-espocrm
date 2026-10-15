<?php

namespace Espo\Custom\Classes\Select\CBgcCheck\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class InVerification implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['bgcStatus' => 'In Verification']);
    }
}
