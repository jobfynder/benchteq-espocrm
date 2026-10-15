<?php

namespace Espo\Custom\Classes\Select\Lead\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

/**
 * Open leads whose next follow-up date is today or earlier.
 */
class FollowUpDue implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where([
            'nextFollowUpDate<=' => gmdate('Y-m-d'),
            'status!=' => ['Converted', 'Dead', 'Recycled'],
        ]);
    }
}
