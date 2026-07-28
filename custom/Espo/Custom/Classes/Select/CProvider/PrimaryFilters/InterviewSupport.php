<?php

namespace Espo\Custom\Classes\Select\CProvider\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\Part\Condition as Cond;
use Espo\ORM\Query\SelectBuilder;

class InterviewSupport implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(
            Cond::like(
                Cond::column('servicesSupplied'),
                '%"Interview Supporter"%'
            )
        );
    }
}
