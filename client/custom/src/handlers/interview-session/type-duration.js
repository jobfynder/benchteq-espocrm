define([], () => {
    // Assessments usually run longer: moving the type to Assessment changes a default
    // 30 minute slot to 90 minutes (and back). A slot the user picked is left alone.
    return class {
        constructor(view) {
            this.view = view;
            this.model = view.model;
        }

        process() {
            this.view.listenTo(this.model, 'change:interviewType', (model, value, options) => {
                if (!options.ui) {
                    return;
                }

                const start = this.model.get('dateStart');
                const end = this.model.get('dateEnd');

                if (!start || !end) {
                    return;
                }

                const current = moment.utc(end).unix() - moment.utc(start).unix();

                if (current !== 1800 && current !== 5400) {
                    return;
                }

                const seconds = value === 'Assessment' ? 5400 : 1800;

                this.model.set(
                    'dateEnd',
                    moment.utc(start).add(seconds, 'seconds').format('YYYY-MM-DD HH:mm:ss'),
                    {ui: true}
                );
            });
        }
    };
});
