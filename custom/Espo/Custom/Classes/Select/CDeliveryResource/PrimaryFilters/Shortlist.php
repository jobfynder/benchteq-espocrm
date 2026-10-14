<?php

namespace Espo\Custom\Classes\Select\CDeliveryResource\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class Shortlist implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['screeningResult' => 'Passed']);
    }
}
