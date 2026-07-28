define(['views/fields/link'], (LinkFieldView) => {
    return class extends LinkFieldView {
        setup() {
            super.setup();

            this.updateProviderFilter();
            this.listenTo(
                this.model,
                'change:serviceType',
                () => this.updateProviderFilter()
            );
        }

        updateProviderFilter() {
            const filterMap = {
                'Interview Support': 'interviewSupport',
                'Job Support': 'jobSupport',
                'BGC': 'bgc',
            };

            this.selectPrimaryFilterName =
                filterMap[this.model.get('serviceType')] || null;
        }
    };
});
