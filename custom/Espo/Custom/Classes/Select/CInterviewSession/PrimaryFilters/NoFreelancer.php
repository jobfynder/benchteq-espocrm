<?php

namespace Espo\Custom\Classes\Select\CInterviewSession\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class NoFreelancer implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['freelancerId' => null, 'status!=' => 'Cancelled']);
    }
}
