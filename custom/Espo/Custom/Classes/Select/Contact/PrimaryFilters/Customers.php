<?php

namespace Espo\Custom\Classes\Select\Contact\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

/**
 * Everyone who has taken at least one of our services.
 */
class Customers implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['customerStatus!=' => 'Prospect']);
    }
}
